"""Provision a load-test user and print their API key.

By default the user gets all three limits cleared (unlimited) — a load run
would trip the conservative defaults instantly. DATABASE_PATH selects the
database, matching how the server is started.

Run from the repo root: DATABASE_PATH=... uv run -m load.provision [name] [--rpm N]
"""

import argparse

from app import config, database
from app.services.user_service import UserService


def ensure_user(
    user_service: UserService, name: str, limits: dict[str, int | float | None]
):
    user = user_service.get_user_by_name(name) or user_service.create_user(name)
    return user_service.update_limits(user.id, limits)


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision a load-test user.")
    parser.add_argument("name", nargs="?", default="load-oha")
    parser.add_argument(
        "--rpm", type=int, default=None, help="requests/minute limit (default: unlimited)"
    )
    args = parser.parse_args()

    connection = database.connect(config.DATABASE_PATH)
    try:
        user = ensure_user(
            UserService(connection),
            args.name,
            {
                "requests_per_minute": args.rpm,
                "tokens_per_day": None,
                "lifetime_spend_dollars": None,
            },
        )
    finally:
        connection.close()
    print(f"name:    {user.name}")
    print(f"limits:  {user.limits()}")
    print(f"api key: {user.token}")


if __name__ == "__main__":
    main()
