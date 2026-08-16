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

The dashboard is served at <http://localhost:8000> — paste an API key: an admin
key opens the fleet view (all users, live limit meters, per-model usage, limit
editing, user creation), a user key shows that user's own usage.

Create users (writes directly to the DB and prints the API key; this is also how
the first admin is created):

```bash
uv run python -m scripts.create_user admin --admin
uv run python -m scripts.create_user alice
```

Then point any OpenAI client at the proxy:

```python
client = openai.OpenAI(base_url="http://localhost:8000", api_key="<key from create_user>")
```

Or use the request script:

```bash
uv run python -m scripts.chat <api-key> "Say hello" [--model llama3.2:1b] [--stream]
```

## Tests & demo

```bash
uv run pytest               # unit tests (Ollama mocked)
uv run python -m scripts.demo   # live proof: chat, streaming, vision, all three limits
                                # (requires the proxy and Ollama running)
```

## Project layout

```
app/            FastAPI proxy: models/, services/, views/ (auth, forwarding, limits, billing)
frontend/       React + TypeScript + Vite dashboard (built to frontend/dist/)
scripts/        create_user.py, chat.py, demo.py (end-to-end proof via the openai client)
tests/          pytest suite, one test per endpoint/behavior
DESIGN.md       Architecture + one section per decision (alternatives, tradeoffs, why)
```

Dependencies are pinned exactly (`pyproject.toml` / `package.json`, with `uv.lock` / `bun.lock` committed). Frontend code is formatted with Prettier (`bun run format`).
