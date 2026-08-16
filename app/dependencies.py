from fastapi import Request

from app.models.user import User

# These must stay async: sync dependencies run in FastAPI's threadpool, which
# would hit the single sqlite connection from many threads at once. Async keeps
# every DB call on the event-loop thread — serialized by construction.


async def get_current_user(request: Request) -> User:
    return request.app.state.user_service.authenticate(
        request.headers.get("authorization")
    )


async def get_admin_user(request: Request) -> User:
    user = await get_current_user(request)
    request.app.state.user_service.require_admin(user)
    return user
