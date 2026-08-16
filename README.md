# llm-proxy

An OpenAI-compatible LLM proxy with per-user API tokens, token-usage tracking, billing, configurable usage limits, and an admin/usage dashboard. Requests are forwarded to a local [Ollama](https://ollama.com) server, which stands in for cloud LLM providers. See [DESIGN.md](DESIGN.md) for architecture and every decision's tradeoffs.

## Prerequisites

- [Homebrew](https://brew.sh) (macOS)
- [uv](https://docs.astral.sh/uv/) — Python toolchain (`brew install uv`)
- [Bun](https://bun.sh) — frontend toolchain (`brew install oven-sh/bun/bun`); Vite runs under Bun's runtime, so no specific Node version is required

## Setup

### 1. Ollama (the model server)

```bash
brew install ollama
brew services start ollama     # serves on :11434
ollama pull llama3.2:1b        # ~1.3 GB — chat model
ollama pull moondream          # ~1.7 GB — vision model
```

### 2. Backend (the proxy)

```bash
uv sync --all-groups           # creates .venv with pinned deps
```

### 3. Frontend (admin/usage dashboard)

```bash
cd frontend
bun install
bun run build                  # outputs frontend/dist/, served by the proxy
```

## Run

```bash
uv run uvicorn app.main:app --port 8000
```

Smoke test: `curl http://localhost:8000/healthz`

## Project layout

```
app/            FastAPI proxy: auth, forwarding, usage tracking, limits, admin API
frontend/       React + TypeScript + Vite dashboard (built to frontend/dist/)
DESIGN.md       Architecture + one section per decision (alternatives, tradeoffs, why)
```

Dependencies are pinned exactly (`pyproject.toml` / `package.json`, with `uv.lock` / `bun.lock` committed).
