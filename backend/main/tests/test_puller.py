import asyncio
from pathlib import Path
import sys
import time

import httpx
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from config import Settings
from db import Database
from puller import pull_trades


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        mock_bse_url="http://mock-bse",
        db_path=str(tmp_path / "tradestream.db"),
        page_request_timeout=1,
        frontend_origin="http://localhost:5173",
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


def response(trades: list[dict[str, object]], next_cursor: str | None, page: int) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "trades": trades,
            "next_cursor": next_cursor,
            "total": 3,
            "page": page,
            "total_pages": 2,
        },
    )


async def no_wait(_: float) -> None:
    return None


def run_pull(
    database: Database,
    settings: Settings,
    transport: httpx.AsyncBaseTransport,
) -> None:
    run = database.start_or_resume_run()
    asyncio.run(pull_trades(database, settings, run, transport=transport, sleep=no_wait))


def test_full_pull_saves_all_trades_without_duplicates(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    database = Database(settings.db_path)
    database.initialize()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("cursor") is None:
            return response([trade("T1"), trade("T2")], "cursor-2", 1)
        return response([trade("T3")], None, 2)

    run_pull(database, settings, httpx.MockTransport(handler))

    assert database.count_trades() == 3
    assert database.latest_run()["status"] == "completed"


def test_trades_endpoint_returns_saved_data_during_pull(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("cursor") is None:
            return response([trade("T1"), trade("T2")], "cursor-2", 1)
        await asyncio.sleep(0.4)
        return response([trade("T3")], None, 2)

    with TestClient(create_app(settings, httpx.MockTransport(handler))) as client:
        time.sleep(0.08)
        started = time.perf_counter()
        result = client.get("/trades")
        elapsed = time.perf_counter() - started
        status = client.get("/pull/status").json()

    assert result.status_code == 200
    assert len(result.json()["trades"]) == 2
    assert elapsed < 0.2
    assert status["status"] == "running"


def test_page_failing_twice_then_succeeding_completes(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    database = Database(settings.db_path)
    database.initialize()
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls <= 2:
            return httpx.Response(503, json={"detail": "temporary outage"})
        return response([trade("T1")], None, 1)

    run_pull(database, settings, httpx.MockTransport(handler))

    assert calls == 3
    assert database.latest_run()["status"] == "completed"
    assert database.count_trades() == 1


def test_failed_page_marks_run_failed_and_keeps_saved_trades(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    database = Database(settings.db_path)
    database.initialize()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("cursor") is None:
            return response([trade("T1")], "cursor-2", 1)
        return httpx.Response(503, json={"detail": "unavailable"})

    run_pull(database, settings, httpx.MockTransport(handler))

    run = database.latest_run()
    assert run["status"] == "failed"
    assert run["last_cursor"] == "cursor-2"
    assert database.count_trades() == 1


def test_resume_uses_last_cursor_without_resaving_prior_pages(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    database = Database(settings.db_path)
    database.initialize()
    initial_calls: list[str | None] = []

    def failing_handler(request: httpx.Request) -> httpx.Response:
        cursor = request.url.params.get("cursor")
        initial_calls.append(cursor)
        if cursor is None:
            return response([trade("T1"), trade("T2")], "cursor-2", 1)
        return httpx.Response(503)

    run_pull(database, settings, httpx.MockTransport(failing_handler))
    first_run_id = database.latest_run()["id"]

    resumed_calls: list[str | None] = []

    def resume_handler(request: httpx.Request) -> httpx.Response:
        resumed_calls.append(request.url.params.get("cursor"))
        return response([trade("T3")], None, 2)

    run_pull(database, settings, httpx.MockTransport(resume_handler))

    assert initial_calls[0] is None
    assert resumed_calls == ["cursor-2"]
    assert database.latest_run()["id"] == first_run_id
    assert database.count_trades() == 3


def test_post_pull_while_running_does_not_start_a_second_pull(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)

    async def handler(_: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.4)
        return response([trade("T1")], None, 1)

    with TestClient(
        create_app(settings, httpx.MockTransport(handler), start_on_startup=False)
    ) as client:
        first = client.post("/pull")
        second = client.post("/pull")

    assert first.status_code == 202
    assert second.status_code == 200
    assert second.json()["status"] == "running"
