import asyncio
from contextlib import asynccontextmanager, suppress

import httpx

from fastapi import FastAPI, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware

from config import Settings, load_settings
from db import Database
from puller import pull_trades


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
        app.state.pull_task = None
        if start_on_startup:
            _start_pull(app, active_settings, transport)
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
    ) -> dict[str, object]:
        return {
            "trades": request.app.state.database.list_trades(limit, offset),
            "limit": limit,
            "offset": offset,
        }

    return app


def _start_pull(
    app: FastAPI, settings: Settings, transport: httpx.AsyncBaseTransport | None
) -> tuple[bool, dict[str, object]]:
    task: asyncio.Task[None] | None = app.state.pull_task
    if task and not task.done():
        return False, _status_payload(app.state.database.latest_run())

    run = app.state.database.start_or_resume_run()
    app.state.pull_task = asyncio.create_task(
        pull_trades(app.state.database, settings, run, transport=transport)
    )
    return True, _status_payload(run)


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


def _json_response(payload: dict[str, object], status_code: int):
    from fastapi.responses import JSONResponse

    return JSONResponse(content=payload, status_code=status_code)

app = create_app()
