from fastapi import FastAPI

app = FastAPI(title="llm-proxy")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
