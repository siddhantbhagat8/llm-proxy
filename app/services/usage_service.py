import sqlite3
import time

from app import config
from app.models.usage_event import UsageEvent


class UsageService:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    @staticmethod
    def cost_dollars(model: str, prompt_tokens: int, completion_tokens: int) -> float:
        prices = config.PRICE_SHEET[model]
        return (
            prompt_tokens * prices["input"] + completion_tokens * prices["output"]
        ) / 1_000_000

    def record(
        self, user_id: int, model: str, prompt_tokens: int, completion_tokens: int
    ) -> UsageEvent:
        created_at = time.time()
        cost = self.cost_dollars(model, prompt_tokens, completion_tokens)
        cursor = self.connection.execute(
            "INSERT INTO usage_events (user_id, model, prompt_tokens, completion_tokens,"
            " cost_dollars, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, model, prompt_tokens, completion_tokens, cost, created_at),
        )
        row = self.connection.execute(
            "SELECT * FROM usage_events WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return UsageEvent.from_row(row)

    def requests_in_window(
        self, user_id: int, window_seconds: int
    ) -> tuple[int, float | None]:
        row = self.connection.execute(
            "SELECT COUNT(*), MIN(created_at) FROM usage_events WHERE user_id = ? AND created_at > ?",
            (user_id, time.time() - window_seconds),
        ).fetchone()
        return row[0], row[1]

    def tokens_in_window(
        self, user_id: int, window_seconds: int
    ) -> tuple[int, float | None]:
        row = self.connection.execute(
            "SELECT COALESCE(SUM(prompt_tokens + completion_tokens), 0), MIN(created_at)"
            " FROM usage_events WHERE user_id = ? AND created_at > ?",
            (user_id, time.time() - window_seconds),
        ).fetchone()
        return row[0], row[1]

    def lifetime_spend_dollars(self, user_id: int) -> float:
        row = self.connection.execute(
            "SELECT COALESCE(SUM(cost_dollars), 0) FROM usage_events WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return row[0]

    def summary(self, user_id: int) -> dict:
        requests_last_minute, _ = self.requests_in_window(user_id, 60)
        tokens_last_day, _ = self.tokens_in_window(user_id, 86400)
        row = self.connection.execute(
            "SELECT COUNT(*), COALESCE(SUM(prompt_tokens + completion_tokens), 0),"
            " COALESCE(SUM(cost_dollars), 0) FROM usage_events WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        by_model = {
            model_row[0]: {
                "requests": model_row[1],
                "prompt_tokens": model_row[2],
                "completion_tokens": model_row[3],
                "cost_dollars": round(model_row[4], 6),
            }
            for model_row in self.connection.execute(
                "SELECT model, COUNT(*), COALESCE(SUM(prompt_tokens), 0),"
                " COALESCE(SUM(completion_tokens), 0), COALESCE(SUM(cost_dollars), 0)"
                " FROM usage_events WHERE user_id = ? GROUP BY model ORDER BY model",
                (user_id,),
            )
        }
        return {
            "requests_last_minute": requests_last_minute,
            "tokens_last_day": tokens_last_day,
            "total_requests": row[0],
            "lifetime_tokens": row[1],
            "lifetime_spend_dollars": round(row[2], 6),
            "by_model": by_model,
        }
