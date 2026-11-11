import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from config import Settings
from db import Database

logger = logging.getLogger("uvicorn.error")
OnPageSaved = Callable[[list[dict[str, Any]]], Awaitable[None]]
OnRunFinished = Callable[[dict[str, Any]], Awaitable[None]]


async def log_page_saved(trades: list[dict[str, Any]]) -> None:
    logger.info("Saved Mock BSE page containing %s trades", len(trades))


async def log_run_finished(run: dict[str, Any]) -> None:
    logger.info("Pull run %s finished with status %s", run["id"], run["status"])


async def pull_trades(
    database: Database,
    settings: Settings,
    run: dict[str, Any],
    on_page_saved: OnPageSaved = log_page_saved,
    on_run_finished: OnRunFinished = log_run_finished,
    transport: httpx.AsyncBaseTransport | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    cursor = run["last_cursor"]
    run_id = int(run["id"])
    url = f"{settings.mock_bse_url.rstrip('/')}/getTrades"

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(settings.page_request_timeout), transport=transport
        ) as client:
            while True:
                payload = await _fetch_page(client, url, cursor, sleep)
                trades = payload["trades"]
                next_cursor = payload["next_cursor"]
                saved_trades = database.save_page(
                    run_id=run_id,
                    trades=trades,
                    next_cursor=next_cursor,
                    total_pages=int(payload["total_pages"]),
                )
                await on_page_saved(saved_trades)

                if next_cursor is None:
                    database.mark_completed(run_id)
                    await on_run_finished(database.get_run(run_id))
                    return
                cursor = next_cursor
    except asyncio.CancelledError:
        raise
    except Exception as error:
        logger.exception("Pull run %s failed", run_id)
        database.mark_failed(run_id, str(error))
        await on_run_finished(database.get_run(run_id))


async def _fetch_page(
    client: httpx.AsyncClient,
    url: str,
    cursor: str | None,
    sleep: Callable[[float], Awaitable[None]],
) -> dict[str, Any]:
    params = {"cursor": cursor} if cursor is not None else None
    last_error: Exception | None = None

    for attempt in range(4):
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload.get("trades"), list) or "next_cursor" not in payload:
                raise ValueError("Mock BSE returned an invalid page response")
            return payload
        except (httpx.HTTPError, ValueError) as error:
            last_error = error
            if attempt == 3:
                break
            await sleep(2**attempt)

    raise RuntimeError(f"Page request failed after 4 attempts: {last_error}")
