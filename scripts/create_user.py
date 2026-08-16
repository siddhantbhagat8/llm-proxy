"""Create a user (or admin) and print their API key.

Writes directly to the database — no running server needed — which is also how
the first admin gets created (the admin API itself requires an admin key).

Run from the repo root: uv run python -m scripts.create_user <name> [--admin]
"""

import argparse

from app import config, database, errors
from app.services.user_service import UserService


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a proxy user and print their API key."
    )
    parser.add_argument("name")
    parser.add_argument("--admin", action="store_true", help="grant the admin flag")
    args = parser.parse_args()

    connection = database.connect(config.DATABASE_PATH)
    try:
        user = UserService(connection).create_user(args.name, is_admin=args.admin)
    except errors.OpenAIError as error:
        raise SystemExit(f"error: {error}") from None
    finally:
        connection.close()

    print(f"id:      {user.id}")
    print(f"name:    {user.name}")
    print(f"admin:   {user.is_admin}")
    print(f"api key: {user.token}")


if __name__ == "__main__":
    main()
