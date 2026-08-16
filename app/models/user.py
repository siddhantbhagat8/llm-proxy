import sqlite3
from dataclasses import dataclass


@dataclass
class User:
    id: int
    name: str
    token: str
    is_admin: bool
    requests_per_minute: int | None
    tokens_per_day: int | None
    lifetime_spend_dollars: float | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "User":
        return cls(
            id=row["id"],
            name=row["name"],
            token=row["token"],
            is_admin=bool(row["is_admin"]),
            requests_per_minute=row["requests_per_minute"],
            tokens_per_day=row["tokens_per_day"],
            lifetime_spend_dollars=row["lifetime_spend_dollars"],
        )

    def limits(self) -> dict[str, int | float | None]:
        return {
            "requests_per_minute": self.requests_per_minute,
            "tokens_per_day": self.tokens_per_day,
            "lifetime_spend_dollars": self.lifetime_spend_dollars,
        }
