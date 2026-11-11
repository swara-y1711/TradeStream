import asyncio
from contextlib import asynccontextmanager, suppress
from typing import Any

import httpx

from fastapi import FastAPI, Query, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware

from config import Settings, load_settings
from db import Database
from puller import pull_trades
from ws import ConnectionManager


def create_app(
    settings: Settings | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    start_on_startup: bool = True,
) -> FastAPI:
    active_settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.database = Database(active_settings.db_path)
        app.state.database.initialize()
        app.state.connection_manager = ConnectionManager()
        app.state.pull_task = None
        if start_on_startup:
            _resume_or_start_on_startup(app, active_settings, transport)
        yield
        task: asyncio.Task[None] | None = app.state.pull_task
        if task and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title="TradeStream Main Backend", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[active_settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/pull")
    async def start_pull(request: Request):
        started, pull_status = _start_pull(request.app, active_settings, transport)
        return _json_response(pull_status, status.HTTP_202_ACCEPTED if started else status.HTTP_200_OK)

    @app.get("/pull/status")
    async def pull_status(request: Request) -> dict[str, object]:
        pull_run = request.app.state.database.latest_run()
        return _status_payload(pull_run)

    @app.get("/trades")
    async def trades(
        request: Request,
        limit: int = Query(default=100, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
        after_seq: int | None = Query(default=None, ge=0),
    ) -> dict[str, object]:
        saved_trades, total, latest_seq = request.app.state.database.list_trades(
            limit, offset, after_seq
        )
        return {
            "trades": saved_trades,
            "total": total,
            "latest_seq": latest_seq,
        }

    @app.websocket("/ws")
    async def websocket_updates(websocket: WebSocket, after_seq: int = Query(default=0, ge=0)):
        manager: ConnectionManager = websocket.app.state.connection_manager
        await manager.connect(websocket)
        last_replayed_seq = after_seq
        try:
            total, latest_seq = websocket.app.state.database.trade_summary()
            if not await manager.send_direct(
                websocket,
                {
                    "type": "hello",
                    "status": _status_payload(websocket.app.state.database.latest_run()),
                    "latest_seq": latest_seq,
                },
            ):
                return

            while True:
                replayed, total, latest_seq = websocket.app.state.database.list_trades(
                    limit=500, offset=0, after_seq=last_replayed_seq
                )
                if not replayed:
                    break
                if not await manager.send_direct(
                    websocket,
                    {
                        "type": "trades",
                        "trades": replayed,
                        "total": total,
                        "latest_seq": latest_seq,
                    },
                ):
                    return
                last_replayed_seq = int(replayed[-1]["seq"])

            if not await manager.finish_replay(websocket, last_replayed_seq):
                return

            while True:
                try:
                    await asyncio.wait_for(
                        websocket.receive_text(), timeout=active_settings.ws_ping_seconds
                    )
                except TimeoutError:
                    if not await manager.send_direct(websocket, {"type": "ping"}):
                        return
        except WebSocketDisconnect:
            return
        finally:
            manager.disconnect(websocket)

    return app


def _start_pull(
    app: FastAPI, settings: Settings, transport: httpx.AsyncBaseTransport | None
) -> tuple[bool, dict[str, object]]:
    task: asyncio.Task[None] | None = app.state.pull_task
    if task and not task.done():
        return False, _status_payload(app.state.database.latest_run())

    run = app.state.database.create_new_run()
    _launch_pull(app, settings, transport, run)
    return True, _status_payload(run)


def _resume_or_start_on_startup(
    app: FastAPI, settings: Settings, transport: httpx.AsyncBaseTransport | None
) -> None:
    run = app.state.database.resume_latest_run()
    if run is None and app.state.database.latest_run() is None:
        run = app.state.database.create_new_run()
    if run is not None:
        _launch_pull(app, settings, transport, run)


def _launch_pull(
    app: FastAPI,
    settings: Settings,
    transport: httpx.AsyncBaseTransport | None,
    run: dict[str, object],
) -> None:
    async def on_page_saved(saved_trades: list[dict[str, Any]]) -> None:
        manager: ConnectionManager = app.state.connection_manager
        if saved_trades:
            total, latest_seq = app.state.database.trade_summary()
            await manager.broadcast(
                {
                    "type": "trades",
                    "trades": saved_trades,
                    "total": total,
                    "latest_seq": latest_seq,
                }
            )
        await manager.broadcast(_progress_message(app.state.database.latest_run()))

    async def on_run_finished(finished_run: dict[str, Any]) -> None:
        await app.state.connection_manager.broadcast(_progress_message(finished_run))

    app.state.pull_task = asyncio.create_task(
        pull_trades(
            app.state.database,
            settings,
            run,
            on_page_saved=on_page_saved,
            on_run_finished=on_run_finished,
            transport=transport,
        )
    )


def _status_payload(run: dict[str, object] | None) -> dict[str, object]:
    if run is None:
        return {
            "status": "idle",
            "pages_done": 0,
            "total_pages": None,
            "trades_saved": 0,
            "error": None,
        }
    return {
        "status": run["status"],
        "pages_done": run["pages_done"],
        "total_pages": run["total_pages"],
        "trades_saved": run["trades_saved"],
        "error": run["error"],
    }


def _progress_message(run: dict[str, object] | None) -> dict[str, object]:
    return {"type": "progress", **_status_payload(run)}


def _json_response(payload: dict[str, object], status_code: int):
    from fastapi.responses import JSONResponse

    return JSONResponse(content=payload, status_code=status_code)

app = create_app()
