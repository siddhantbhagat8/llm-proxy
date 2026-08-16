from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.dependencies import get_admin_user
from app.models.user import User

router = APIRouter(prefix="/admin")


class CreateUserRequest(BaseModel):
    name: str
    is_admin: bool = False


class UpdateLimitsRequest(BaseModel):
    requests_per_minute: int | None = None
    tokens_per_day: int | None = None
    lifetime_spend_dollars: float | None = None


def _user_payload(request: Request, user: User) -> dict:
    # API keys are exposed to admins by design — plaintext at rest (DESIGN.md 3.6).
    return {
        "id": user.id,
        "name": user.name,
        "is_admin": user.is_admin,
        "api_key": user.token,
        "limits": user.limits(),
        "usage": request.app.state.usage_service.summary(user.id),
    }


@router.get("/users")
async def list_users(
    request: Request, admin: Annotated[User, Depends(get_admin_user)]
) -> list[dict]:
    return [
        _user_payload(request, user)
        for user in request.app.state.user_service.list_users()
    ]


@router.post("/users", status_code=201)
async def create_user(
    request: Request,
    body: CreateUserRequest,
    admin: Annotated[User, Depends(get_admin_user)],
) -> dict:
    user = request.app.state.user_service.create_user(body.name, is_admin=body.is_admin)
    return _user_payload(request, user)


@router.put("/users/{user_id}/limits")
async def update_limits(
    request: Request,
    user_id: int,
    body: UpdateLimitsRequest,
    admin: Annotated[User, Depends(get_admin_user)],
) -> dict:
    # Fields absent from the body are unchanged; explicit nulls clear the limit.
    updates = body.model_dump(exclude_unset=True)
    user = request.app.state.user_service.update_limits(user_id, updates)
    return _user_payload(request, user)
