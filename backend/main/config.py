import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    mock_bse_url: str
    db_path: str
    page_request_timeout: float
    frontend_origin: str


def load_settings() -> Settings:
    timeout = float(os.getenv("PAGE_REQUEST_TIMEOUT", "35"))
    if timeout <= 0:
        raise ValueError("PAGE_REQUEST_TIMEOUT must be greater than zero")

    return Settings(
        mock_bse_url=os.getenv("MOCK_BSE_URL", "http://localhost:8001"),
        db_path=os.getenv("DB_PATH", "./data/tradestream.db"),
        page_request_timeout=timeout,
        frontend_origin=os.getenv("FRONTEND_ORIGIN", "http://localhost:5173"),
    )
