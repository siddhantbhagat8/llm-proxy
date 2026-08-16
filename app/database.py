import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    token TEXT NOT NULL UNIQUE,
    is_admin INTEGER NOT NULL DEFAULT 0,
    requests_per_minute INTEGER,
    tokens_per_day INTEGER,
    lifetime_spend_dollars REAL
);

CREATE TABLE IF NOT EXISTS usage_events (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    model TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    cost_dollars REAL NOT NULL,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS index_usage_events_user_time
    ON usage_events (user_id, created_at);
"""


def connect(database_path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(
        database_path, check_same_thread=False, autocommit=True
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout=5000")
    # busy_timeout does NOT cover journal-mode changes: SQLite fails those
    # immediately under contention (deadlock avoidance), so workers booting
    # against a fresh database race here and need an explicit retry.
    for attempt in range(20):
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            # With WAL, NORMAL risks only the newest writes on an OS crash —
            # acceptable for usage events; avoids an fsync per insert.
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.executescript(SCHEMA)
            break
        except sqlite3.OperationalError:
            if attempt == 19:
                raise
            time.sleep(0.05 * (attempt + 1))
    return connection
