import sqlite3
from dataclasses import dataclass


@dataclass
class UsageEvent:
    id: int
    user_id: int
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_dollars: float
    created_at: float

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "UsageEvent":
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            model=row["model"],
            prompt_tokens=row["prompt_tokens"],
            completion_tokens=row["completion_tokens"],
            cost_dollars=row["cost_dollars"],
            created_at=row["created_at"],
        )
