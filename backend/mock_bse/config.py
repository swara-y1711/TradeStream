import math
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    total_trades: int
    page_size: int
    pull_delay_seconds: float
    seed: int

    @property
    def total_pages(self) -> int:
        return math.ceil(self.total_trades / self.page_size)

    @property
    def per_page_delay_seconds(self) -> float:
        return self.pull_delay_seconds / self.total_pages


def _positive_int(name: str, default: int) -> int:
    value = os.getenv(name, str(default))
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be a positive integer") from error
    if parsed <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return parsed


def _non_negative_float(name: str, default: float) -> float:
    value = os.getenv(name, str(default))
    try:
        parsed = float(value)
    except ValueError as error:
        raise ValueError(f"{name} must be a non-negative number") from error
    if parsed < 0:
        raise ValueError(f"{name} must be a non-negative number")
    return parsed


def load_settings() -> Settings:
    return Settings(
        total_trades=_positive_int("TOTAL_TRADES", 5000),
        page_size=_positive_int("PAGE_SIZE", 100),
        pull_delay_seconds=_non_negative_float("PULL_DELAY_SECONDS", 900),
        seed=_positive_int("SEED", 42),
    )


def validate_startup(settings: Settings) -> None:
    if settings.per_page_delay_seconds > 25:
        raise ValueError(
            "Mock BSE configuration is unsafe: per-page delay "
            f"({settings.per_page_delay_seconds:.2f}s) exceeds 25 seconds. "
            "Increase PAGE_SIZE, reduce TOTAL_TRADES, or reduce PULL_DELAY_SECONDS."
        )
