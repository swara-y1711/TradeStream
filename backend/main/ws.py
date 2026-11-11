import asyncio
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket


@dataclass
class _Client:
    replaying: bool = True
    buffered: list[dict[str, Any]] = field(default_factory=list)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class ConnectionManager:
    def __init__(self) -> None:
        self._clients: dict[WebSocket, _Client] = {}

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._clients[websocket] = _Client()

    def disconnect(self, websocket: WebSocket) -> None:
        self._clients.pop(websocket, None)

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def broadcast(self, message: dict[str, Any]) -> None:
        await asyncio.gather(
            *(self._send_or_buffer(websocket, message) for websocket in tuple(self._clients)),
            return_exceptions=True,
        )

    async def send_direct(self, websocket: WebSocket, message: dict[str, Any]) -> bool:
        client = self._clients.get(websocket)
        if client is None:
            return False
        try:
            async with client.lock:
                await websocket.send_json(message)
            return True
        except Exception:
            self.disconnect(websocket)
            return False

    async def finish_replay(self, websocket: WebSocket, last_replayed_seq: int) -> bool:
        client = self._clients.get(websocket)
        if client is None:
            return False

        try:
            async with client.lock:
                for message in client.buffered:
                    filtered = _filter_message(message, last_replayed_seq)
                    if filtered is None:
                        continue
                    await websocket.send_json(filtered)
                    if filtered["type"] == "trades":
                        last_replayed_seq = int(filtered["trades"][-1]["seq"])
                client.buffered.clear()
                client.replaying = False
            return True
        except Exception:
            self.disconnect(websocket)
            return False

    async def _send_or_buffer(self, websocket: WebSocket, message: dict[str, Any]) -> None:
        client = self._clients.get(websocket)
        if client is None:
            return
        try:
            async with client.lock:
                if client.replaying:
                    client.buffered.append(message)
                else:
                    await websocket.send_json(message)
        except Exception:
            self.disconnect(websocket)


def _filter_message(message: dict[str, Any], last_replayed_seq: int) -> dict[str, Any] | None:
    if message.get("type") != "trades":
        return message

    trades = [trade for trade in message["trades"] if int(trade["seq"]) > last_replayed_seq]
    if not trades:
        return None
    return {**message, "trades": trades, "latest_seq": trades[-1]["seq"]}
