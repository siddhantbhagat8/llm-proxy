import json
from collections.abc import AsyncIterator

import httpx
from fastapi import Response
from fastapi.responses import StreamingResponse

from app import config, errors
from app.models.user import User
from app.services.usage_service import UsageService


class ProxyService:
    """Forwards chat completions to Ollama and records usage from the response."""

    def __init__(self, client: httpx.AsyncClient, usage_service: UsageService) -> None:
        self.client = client
        self.usage_service = usage_service

    async def chat_completion(self, user: User, payload: dict) -> Response:
        model = payload.get("model")
        if not isinstance(model, str) or model not in config.PRICE_SHEET:
            raise errors.model_not_found(str(model))
        # Ollama serves the OpenAI-compat API only under /v1; openai clients send bare paths.
        if payload.get("stream"):
            return await self._streamed(user, model, payload)
        upstream = await self.client.post("/v1/chat/completions", json=payload)
        if upstream.status_code == 200:
            usage = upstream.json().get("usage")
            if usage:
                self.usage_service.record(
                    user.id, model, usage["prompt_tokens"], usage["completion_tokens"]
                )
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            media_type=upstream.headers.get("content-type"),
        )

    async def _streamed(self, user: User, model: str, payload: dict) -> Response:
        # Without include_usage, streamed responses carry no usage at all.
        payload.setdefault("stream_options", {})["include_usage"] = True
        request = self.client.build_request(
            "POST", "/v1/chat/completions", json=payload
        )
        upstream = await self.client.send(request, stream=True)
        if upstream.status_code != 200:
            content = await upstream.aread()
            await upstream.aclose()
            return Response(
                content=content,
                status_code=upstream.status_code,
                media_type=upstream.headers.get("content-type"),
            )
        return StreamingResponse(
            self._relay(user, model, upstream), media_type="text/event-stream"
        )

    async def _relay(
        self, user: User, model: str, upstream: httpx.Response
    ) -> AsyncIterator[str]:
        usage = None
        try:
            async for line in upstream.aiter_lines():
                if line.startswith("data: ") and not line.startswith("data: [DONE]"):
                    chunk = json.loads(line[len("data: ") :])
                    if chunk.get("usage"):
                        usage = chunk["usage"]
                yield line + "\n"
        finally:
            await upstream.aclose()
        if usage:
            self.usage_service.record(
                user.id, model, usage["prompt_tokens"], usage["completion_tokens"]
            )
