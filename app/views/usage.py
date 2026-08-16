from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/usage")
async def get_usage(
    request: Request, user: Annotated[User, Depends(get_current_user)]
) -> dict:
    return {
        "user": {"id": user.id, "name": user.name},
        "limits": user.limits(),
        "usage": request.app.state.usage_service.summary(user.id),
    }
