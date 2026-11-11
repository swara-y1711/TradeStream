from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from config import Settings
from seed_data import generate_trades


def settings(**overrides: int | float) -> Settings:
    values: dict[str, int | float] = {
        "total_trades": 13,
        "page_size": 5,
        "pull_delay_seconds": 0,
        "seed": 42,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_all_pages_return_every_trade_once() -> None:
    with TestClient(create_app(settings())) as client:
        cursor: str | None = None
        trades: list[dict[str, object]] = []
        while True:
            response = client.get("/getTrades", params={"cursor": cursor} if cursor else {})
            assert response.status_code == 200
            payload = response.json()
            trades.extend(payload["trades"])
            cursor = payload["next_cursor"]
            if cursor is None:
                break

    assert len(trades) == 13
    assert len({trade["trade_id"] for trade in trades}) == 13


def test_last_page_has_null_next_cursor() -> None:
    with TestClient(create_app(settings())) as client:
        first_cursor = client.get("/getTrades").json()["next_cursor"]
        second_cursor = client.get("/getTrades", params={"cursor": first_cursor}).json()[
            "next_cursor"
        ]
        last_page = client.get("/getTrades", params={"cursor": second_cursor}).json()

    assert last_page["next_cursor"] is None
    assert last_page["page"] == 3
    assert last_page["total_pages"] == 3


def test_invalid_cursor_returns_400() -> None:
    with TestClient(create_app(settings())) as client:
        response = client.get("/getTrades", params={"cursor": "not-a-valid-cursor"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid cursor"


def test_same_seed_generates_identical_data() -> None:
    first = generate_trades(settings(seed=99))
    second = generate_trades(settings(seed=99))

    assert first == second


def test_startup_fails_when_page_delay_exceeds_limit() -> None:
    unsafe_settings = settings(total_trades=100, page_size=100, pull_delay_seconds=26)

    with pytest.raises(ValueError, match="exceeds 25 seconds"):
        with TestClient(create_app(unsafe_settings)):
            pass
