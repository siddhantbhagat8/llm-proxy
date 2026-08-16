import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import config, database
from app.errors import OpenAIError
from app.services.limit_service import LimitService
from app.services.proxy_service import ProxyService
from app.services.usage_service import UsageService
from app.services.user_service import UserService
from app.views import admin, chat, usage


def create_app(
    database_path: str | None = None,
    ollama_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        connection = database.connect(database_path or config.DATABASE_PATH)
        client = httpx.AsyncClient(
            base_url=config.OLLAMA_BASE_URL,
            timeout=httpx.Timeout(connect=5, read=300, write=30, pool=5),
            # Default pool caps at 100 connections — the proxy would throttle
            # itself below the hundreds of concurrent requests it must hold.
            limits=httpx.Limits(max_connections=1000, max_keepalive_connections=100),
            transport=ollama_transport,
        )
        user_service = UserService(connection)
        usage_service = UsageService(connection)
        app.state.user_service = user_service
        app.state.usage_service = usage_service
        app.state.limit_service = LimitService(usage_service)
        app.state.proxy_service = ProxyService(client, usage_service)
        yield
        await client.aclose()
        connection.close()

    app = FastAPI(title="llm-proxy", lifespan=lifespan)

    @app.exception_handler(OpenAIError)
    async def openai_error_handler(
        request: Request, exception: OpenAIError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exception.status_code,
            content=exception.body(),
            headers=exception.headers,
        )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(chat.router)
    app.include_router(usage.router)
    app.include_router(admin.router)

    if os.path.isdir(config.FRONTEND_DIST_DIRECTORY):
        app.mount(
            "/",
            StaticFiles(directory=config.FRONTEND_DIST_DIRECTORY, html=True),
            name="frontend",
        )

    return app


app = create_app()
