import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Database:
    def __init__(self, path: str) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS trades (
                    trade_id TEXT PRIMARY KEY,
                    client TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    price REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    pulled_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS pull_runs (
                    id INTEGER PRIMARY KEY,
                    status TEXT NOT NULL CHECK(status IN ('running', 'completed', 'failed')),
                    last_cursor TEXT,
                    pages_done INTEGER NOT NULL DEFAULT 0,
                    total_pages INTEGER,
                    trades_saved INTEGER NOT NULL DEFAULT 0,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    error TEXT
                )
                """
            )

    def start_or_resume_run(self) -> dict[str, Any]:
        latest = self.latest_run()
        now = _now()
        if latest and (
            latest["status"] == "running"
            or (latest["status"] == "failed" and latest["last_cursor"] is not None)
        ):
            with self._connect() as connection:
                connection.execute(
                    "UPDATE pull_runs SET status = 'running', error = NULL, finished_at = NULL WHERE id = ?",
                    (latest["id"],),
                )
            return self.get_run(int(latest["id"]))

        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO pull_runs (status, started_at) VALUES ('running', ?)",
                (now,),
            )
            run_id = int(cursor.lastrowid)
        return self.get_run(run_id)

    def save_page(
        self,
        run_id: int,
        trades: list[dict[str, Any]],
        next_cursor: str | None,
        total_pages: int,
    ) -> int:
        pulled_at = _now()
        rows = [
            (
                trade["trade_id"],
                trade["client"],
                trade["symbol"],
                trade["quantity"],
                trade["price"],
                trade["timestamp"],
                pulled_at,
            )
            for trade in trades
        ]
        with self._connect() as connection:
            before = connection.total_changes
            connection.executemany(
                """
                INSERT OR IGNORE INTO trades
                    (trade_id, client, symbol, quantity, price, timestamp, pulled_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            inserted = connection.total_changes - before
            connection.execute(
                """
                UPDATE pull_runs
                SET last_cursor = ?, pages_done = pages_done + 1,
                    total_pages = ?, trades_saved = trades_saved + ?
                WHERE id = ?
                """,
                (next_cursor, total_pages, inserted, run_id),
            )
        return inserted

    def mark_completed(self, run_id: int) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE pull_runs SET status = 'completed', finished_at = ?, last_cursor = NULL WHERE id = ?",
                (_now(), run_id),
            )

    def mark_failed(self, run_id: int, error: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE pull_runs SET status = 'failed', finished_at = ?, error = ? WHERE id = ?",
                (_now(), error, run_id),
            )

    def latest_run(self) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM pull_runs ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def get_run(self, run_id: int) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM pull_runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            raise LookupError(f"Pull run {run_id} does not exist")
        return dict(row)

    def list_trades(self, limit: int, offset: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM trades ORDER BY timestamp DESC, trade_id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(row) for row in rows]

    def count_trades(self) -> int:
        with self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM trades").fetchone()[0])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
