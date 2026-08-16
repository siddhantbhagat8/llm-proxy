from fastapi import Request

from app.models.user import User


def get_current_user(request: Request) -> User:
    return request.app.state.user_service.authenticate(
        request.headers.get("authorization")
    )


def get_admin_user(request: Request) -> User:
    user = get_current_user(request)
    request.app.state.user_service.require_admin(user)
    return user
