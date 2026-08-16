import secrets
import sqlite3

from app import config, errors
from app.models.user import User

LIMIT_COLUMNS = ("requests_per_minute", "tokens_per_day", "lifetime_spend_dollars")


class UserService:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def authenticate(self, authorization_header: str | None) -> User:
        if authorization_header is None:
            raise errors.invalid_api_key(
                "You didn't provide an API key. You need to provide your API key in an "
                "Authorization header using Bearer auth (i.e. Authorization: Bearer YOUR_KEY)."
            )
        scheme, _, token = authorization_header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise errors.invalid_api_key(
                "Invalid Authorization header format. Expected: Bearer YOUR_KEY."
            )
        row = self.connection.execute(
            "SELECT * FROM users WHERE token = ?", (token,)
        ).fetchone()
        if row is None:
            raise errors.invalid_api_key(
                f"Incorrect API key provided: {token[:12]}***."
            )
        return User.from_row(row)

    def require_admin(self, user: User) -> None:
        if not user.is_admin:
            raise errors.admin_required()

    def create_user(
        self, name: str, is_admin: bool = False, token: str | None = None
    ) -> User:
        token = token or f"sk-proxy-{secrets.token_hex(16)}"
        try:
            cursor = self.connection.execute(
                "INSERT INTO users (name, token, is_admin, requests_per_minute,"
                " tokens_per_day, lifetime_spend_dollars) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    name,
                    token,
                    int(is_admin),
                    config.DEFAULT_REQUESTS_PER_MINUTE,
                    config.DEFAULT_TOKENS_PER_DAY,
                    config.DEFAULT_LIFETIME_SPEND_DOLLARS,
                ),
            )
        except sqlite3.IntegrityError:
            raise errors.OpenAIError(
                400,
                f"A user named '{name}' already exists.",
                "invalid_request_error",
                "user_already_exists",
            ) from None
        user = self.get_user(cursor.lastrowid)
        assert user is not None
        return user

    def get_user(self, user_id: int | None) -> User | None:
        row = self.connection.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return User.from_row(row) if row else None

    def get_user_by_name(self, name: str) -> User | None:
        row = self.connection.execute(
            "SELECT * FROM users WHERE name = ?", (name,)
        ).fetchone()
        return User.from_row(row) if row else None

    def list_users(self) -> list[User]:
        rows = self.connection.execute("SELECT * FROM users ORDER BY id").fetchall()
        return [User.from_row(row) for row in rows]

    def update_limits(
        self, user_id: int, updates: dict[str, int | float | None]
    ) -> User:
        user = self.get_user(user_id)
        if user is None:
            raise errors.OpenAIError(
                404,
                f"No user with id {user_id}.",
                "invalid_request_error",
                "user_not_found",
            )
        columns = [column for column in LIMIT_COLUMNS if column in updates]
        if columns:
            set_clause = ", ".join(f"{column} = ?" for column in columns)
            values = [updates[column] for column in columns]
            self.connection.execute(
                f"UPDATE users SET {set_clause} WHERE id = ?", (*values, user_id)
            )
        updated = self.get_user(user_id)
        assert updated is not None
        return updated
