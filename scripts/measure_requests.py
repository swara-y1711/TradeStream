# Development-only tool for measuring paginated Mock BSE request durations.
"""Print the duration of every Mock BSE page request plus min/max/average."""

from __future__ import annotations

import json
import sys
import time
from statistics import mean
from urllib.parse import urlencode
from urllib.request import urlopen


def fetch_pages(base_url: str) -> list[float]:
    cursor: str | None = None
    durations: list[float] = []

    while True:
        query = urlencode({"cursor": cursor}) if cursor else ""
        url = f"{base_url.rstrip('/')}/getTrades" + (f"?{query}" if query else "")
        started = time.perf_counter()
        with urlopen(url, timeout=30) as response:  # noqa: S310 - explicit local development URL
            payload = json.load(response)
        duration = time.perf_counter() - started
        durations.append(duration)
        print(f"page {payload['page']}/{payload['total_pages']}: {duration:.2f}s")
        cursor = payload["next_cursor"]
        if cursor is None:
            return durations


def main() -> None:
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001"
    durations = fetch_pages(base_url)
    print(
        "summary: "
        f"pages={len(durations)}, min={min(durations):.2f}s, "
        f"max={max(durations):.2f}s, avg={mean(durations):.2f}s"
    )


if __name__ == "__main__":
    main()
