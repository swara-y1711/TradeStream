import asyncio
from pathlib import Path
import sys

import httpx
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from config import Settings
from db import Database
from ws import ConnectionManager


def settings(tmp_path: Path) -> Settings:
    return Settings(
        mock_bse_url="http://mock-bse",
        db_path=str(tmp_path / "tradestream.db"),
        page_request_timeout=1,
        frontend_origin="http://localhost:5173",
        ws_ping_seconds=60,
    )


def trade(trade_id: str) -> dict[str, object]:
    return {
        "trade_id": trade_id,
        "client": "CLT-1001",
        "symbol": "RELIANCE",
        "quantity": 10,
        "price": 1200.50,
        "timestamp": "2024-01-02T09:15:00+05:30",
    }


def page(trades: list[dict[str, object]], next_cursor: str | None) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "trades": trades,
            "next_cursor": next_cursor,
            "total": len(trades),
            "page": 1,
            "total_pages": 1,
        },
    )


def seed_completed(database: Database, trades: list[dict[str, object]]) -> None:
    run = database.create_new_run()
    database.save_page(int(run["id"]), trades, None, 1)
    database.mark_completed(int(run["id"]))


def test_client_connected_before_save_receives_live_trades_and_final_progress(tmp_path: Path) -> None:
    active_settings = settings(tmp_path)

    async def handler(_: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.1)
        return page([trade("T1")], None)

    with TestClient(create_app(active_settings, httpx.MockTransport(handler))) as client:
        with client.websocket_connect("/ws") as websocket:
            assert websocket.receive_json()["type"] == "hello"
            trades_message = websocket.receive_json()
            running_progress = websocket.receive_json()
            completed_progress = websocket.receive_json()

    assert trades_message["type"] == "trades"
    assert [row["trade_id"] for row in trades_message["trades"]] == ["T1"]
    assert running_progress == {
        "type": "progress",
        "status": "running",
        "pages_done": 1,
        "total_pages": 1,
        "trades_saved": 1,
        "error": None,
    }
    assert completed_progress["type"] == "progress"
    assert completed_progress["status"] == "completed"


def test_after_seq_replays_only_newer_trades(tmp_path: Path) -> None:
    active_settings = settings(tmp_path)
    database = Database(active_settings.db_path)
    database.initialize()
    seed_completed(database, [trade("T1"), trade("T2"), trade("T3")])

    with TestClient(create_app(active_settings, start_on_startup=False)) as client:
        with client.websocket_connect("/ws?after_seq=1") as websocket:
            hello = websocket.receive_json()
            replay = websocket.receive_json()

    assert hello["type"] == "hello"
    assert [row["seq"] for row in replay["trades"]] == [2, 3]
    assert [row["trade_id"] for row in replay["trades"]] == ["T2", "T3"]


class FakeWebSocket:
    def __init__(self, fail_on_send: bool = False) -> None:
        self.fail_on_send = fail_on_send
        self.messages: list[dict[str, object]] = []

    async def accept(self) -> None:
        return None

    async def send_json(self, message: dict[str, object]) -> None:
        if self.fail_on_send:
            raise RuntimeError("closed")
        self.messages.append(message)


def test_buffered_live_page_has_no_gap_or_duplicate_during_replay() -> None:
    async def scenario() -> list[dict[str, object]]:
        manager = ConnectionManager()
        websocket = FakeWebSocket()
        await manager.connect(websocket)  # type: ignore[arg-type]
        await manager.send_direct(  # type: ignore[arg-type]
            websocket,
            {"type": "trades", "trades": [{"seq": 1}, {"seq": 2}], "total": 2, "latest_seq": 2},
        )
        await manager.broadcast(
            {"type": "trades", "trades": [{"seq": 3}], "total": 3, "latest_seq": 3}
        )
        await manager.finish_replay(websocket, 2)  # type: ignore[arg-type]
        return websocket.messages

    messages = asyncio.run(scenario())
    sequences = [row["seq"] for message in messages if message["type"] == "trades" for row in message["trades"]]

    assert sequences == [1, 2, 3]
    assert len(sequences) == len(set(sequences))


def test_failed_client_is_removed_without_stopping_other_clients() -> None:
    async def scenario() -> tuple[int, list[dict[str, object]], int]:
        manager = ConnectionManager()
        good_client = FakeWebSocket()
        bad_client = FakeWebSocket(fail_on_send=True)
        await manager.connect(good_client)  # type: ignore[arg-type]
        await manager.connect(bad_client)  # type: ignore[arg-type]
        await manager.finish_replay(good_client, 0)  # type: ignore[arg-type]
        await manager.finish_replay(bad_client, 0)  # type: ignore[arg-type]
        await manager.broadcast({"type": "progress", "status": "running"})
        await manager.broadcast({"type": "progress", "status": "completed"})
        return manager.client_count, good_client.messages, len(bad_client.messages)

    client_count, good_messages, bad_messages = asyncio.run(scenario())

    assert client_count == 1
    assert [message["status"] for message in good_messages] == ["running", "completed"]
    assert bad_messages == 0


def test_pull_completes_with_no_websocket_clients(tmp_path: Path) -> None:
    active_settings = settings(tmp_path)

    def handler(_: httpx.Request) -> httpx.Response:
        return page([trade("T1")], None)

    with TestClient(create_app(active_settings, httpx.MockTransport(handler))) as client:
        status = client.get("/pull/status").json()
        for _ in range(10):
            if status["status"] == "completed":
                break
            status = client.get("/pull/status").json()

    assert status["status"] == "completed"
