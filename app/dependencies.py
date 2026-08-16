from fastapi import Request

from app.models.user import User

# Must stay async: sync dependencies run in FastAPI's threadpool, which would
# hit the single sqlite connection from multiple threads at once.


async def get_current_user(request: Request) -> User:
    return request.app.state.user_service.authenticate(
        request.headers.get("authorization")
    )


async def get_admin_user(request: Request) -> User:
    user = await get_current_user(request)
    request.app.state.user_service.require_admin(user)
    return user
