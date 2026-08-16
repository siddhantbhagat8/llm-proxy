# llm-proxy

An OpenAI-compatible LLM proxy with per-user API keys, token-usage tracking, billing, configurable usage limits, and an admin/usage dashboard. Requests are forwarded to a local [Ollama](https://ollama.com) server (`llama3.2:1b` for chat, `moondream` for vision), which stands in for cloud LLM providers.

## Quickstart

Requires [uv](https://docs.astral.sh/uv/), [Bun](https://bun.sh), and [Ollama](https://ollama.com) (all `brew install`-able).

```bash
ollama pull llama3.2:1b && ollama pull moondream    # with the Ollama server running

uv sync --all-groups                                # backend deps
cd frontend && bun install && bun run build && cd ..  # dashboard → frontend/dist/

uv run -m scripts.create_user admin --admin         # prints an API key
uv run uvicorn app.main:app --port 8000
```

Dashboard at `http://localhost:8000` — paste an API key; admins see all users, users see themselves. Point any OpenAI client at `base_url="http://localhost:8000"` with a user's key.

## Project layout

```
app/            FastAPI proxy: models/, services/, views/ (auth, forwarding, limits, billing)
frontend/       React + TypeScript + Vite dashboard (built to frontend/dist/)
scripts/        create_user.py, chat.py (requests via the stock openai client)
load/           stub_upstream.py, provision.py, scenario.py (load and concurrency runs)
tests/          pytest suite, one test per endpoint/behavior
```
