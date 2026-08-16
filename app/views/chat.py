import json
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app import config, errors
from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("/chat/completions")
@router.post("/v1/chat/completions")
async def chat_completions(
    request: Request, user: Annotated[User, Depends(get_current_user)]
) -> Response:
    try:
        payload = json.loads(await request.body())
    except json.JSONDecodeError:
        raise errors.OpenAIError(
            400,
            "Request body is not valid JSON.",
            "invalid_request_error",
            "invalid_json",
        ) from None
    request.app.state.limit_service.check(user)
    return await request.app.state.proxy_service.chat_completion(user, payload)


@router.get("/models")
@router.get("/v1/models")
async def list_models(user: Annotated[User, Depends(get_current_user)]) -> dict:
    # Served from the price sheet, not Ollama: only billable models are offered (DESIGN.md 3.6).
    return {
        "object": "list",
        "data": [
            {"id": model, "object": "model", "created": 0, "owned_by": "llm-proxy"}
            for model in config.PRICE_SHEET
        ],
    }
