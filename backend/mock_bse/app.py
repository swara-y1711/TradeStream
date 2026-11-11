import asyncio
import base64
import binascii
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request

from config import Settings, load_settings, validate_startup
from seed_data import generate_trades

logger = logging.getLogger("uvicorn.error")


def _encode_cursor(offset: int) -> str:
    payload = f"trades:{offset}".encode("ascii")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str | None, settings: Settings) -> int:
    if cursor is None:
        return 0

    try:
        padded_cursor = cursor + "=" * (-len(cursor) % 4)
        decoded = base64.b64decode(
            padded_cursor.encode("ascii"), altchars=b"-_", validate=True
        ).decode("ascii")
        prefix, raw_offset = decoded.split(":", maxsplit=1)
        offset = int(raw_offset)
    except (UnicodeEncodeError, UnicodeDecodeError, binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="Invalid cursor") from None

    if (
        prefix != "trades"
        or offset <= 0
        or offset >= settings.total_trades
        or offset % settings.page_size != 0
    ):
        raise HTTPException(status_code=400, detail="Invalid cursor")
    return offset


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        active_settings = settings or load_settings()
        validate_startup(active_settings)
        app.state.settings = active_settings
        app.state.trades = generate_trades(active_settings)
        logger.info(
            "Mock BSE configured: total trades=%s, page size=%s, total pages=%s, "
            "per-page delay=%.2fs",
            active_settings.total_trades,
            active_settings.page_size,
            active_settings.total_pages,
            active_settings.per_page_delay_seconds,
        )
        yield

    app = FastAPI(title="Mock BSE", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/getTrades")
    async def get_trades(request: Request, cursor: str | None = None) -> dict[str, object]:
        active_settings: Settings = request.app.state.settings
        offset = _decode_cursor(cursor, active_settings)
        await asyncio.sleep(active_settings.per_page_delay_seconds)
        next_offset = offset + active_settings.page_size

        return {
            "trades": request.app.state.trades[offset:next_offset],
            "next_cursor": (
                _encode_cursor(next_offset)
                if next_offset < active_settings.total_trades
                else None
            ),
            "total": active_settings.total_trades,
            "page": offset // active_settings.page_size + 1,
            "total_pages": active_settings.total_pages,
        }

    return app

app = create_app()
