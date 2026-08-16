import sqlite3

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
    connection.execute("PRAGMA journal_mode=WAL")
    connection.executescript(SCHEMA)
    return connection
