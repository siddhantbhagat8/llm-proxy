# Design

An OpenAI-compatible LLM proxy with per-user authentication, token-usage tracking, billing, and configurable usage limits. Each section below records a decision: what was chosen, the alternatives, and why.

## 1. System context

**What Ollama is.** Ollama runs open-source LLMs locally — `ollama pull llama3.2:1b` downloads Meta's Llama 3.2 (1B) weights to disk, and inference runs on the local machine's hardware. No cloud provider is involved.

**"OpenAI-compatible" means format, not destination.** OpenAI's HTTP API shape (`/v1/chat/completions`, its JSON request/response structure) is the de-facto industry standard, so Ollama implements the same interface. Any client built for that format — like the `openai` Python library, which is just an HTTP client — works against Ollama or this proxy by changing `base_url`. No requests ever go to OpenAI.

**How this maps to the real system.** In production, this proxy would forward to actual providers (OpenAI, Anthropic, OpenRouter) and pass through real token costs. Here, Ollama stands in for those providers: free and local, but speaking the same protocol, so the proxy logic (auth, forwarding, streaming, usage accounting, limits) is identical. A per-model price table simulates the billing relationship. There is no model remapping — clients request local models by name (`llama3.2:1b`, `moondream`) and get exactly those.

## 2. Architecture

Three processes, all local:

```
openai client            our proxy (this repo)              Ollama
(HTTP client speaking ─▶ FastAPI on :8000              ─▶   server on :11434
 the OpenAI format)      auth + limits + usage tracking      runs model weights locally
```

Inside the proxy:

```
                       ┌──────────────────────────────────────────────────────┐
                       │              llm-proxy  (FastAPI, :8000)             │
                       │                                                      │
  openai client        │   ┌──────┐   ┌────────┐   ┌───────────────┐          │
  (Bearer: user  ────────▶ │ auth │──▶│ limits │──▶│ forward       │ ───────────▶  Ollama (:11434)
   token)              │   └──┬───┘   └───┬────┘   │ (httpx, adds  │          │    /v1/chat/completions
       ▲               │      │           │        │  /v1 prefix,  │          │    llama3.2:1b, moondream
       │  response/    │      │           │        │  injects      │ ◀────────────  response / SSE stream
       │  SSE stream ◀────────┼───────────┼────────┤  include_usage│          │
       │               │      │           │        │  ) then       │          │
       │               │      │           │        │  streams back │          │
       │               │      │           │        └───────┬───────┘          │
       │               │      ▼           ▼                ▼ usage from       │
       │               │   ┌──────────────────────────────────┐ final chunk   │
       │               │   │   SQLite (WAL)                   │               │
       │               │   │   users / limits / usage_events  │               │
       │               │   └──────────────▲───────────────────┘               │
       │               │                  │                                   │
  React admin UI  ────────▶ /admin/* + /usage JSON APIs                       │
  (Vite build, served  │                                                      │
   statically by       │                                                      │
   FastAPI)            └──────────────────────────────────────────────────────┘
```

### Lifecycle of one streamed chat request

1. Client calls `POST /chat/completions` with `Authorization: Bearer <user-token>`.
2. **Auth** — token looked up in SQLite → user identified, or 401 in OpenAI's error format.
3. **Limit check** — the user's recent/total usage (sums over `usage_events`) is compared against their limits → error response if exceeded.
4. **Forward** — httpx sends the JSON body to `http://localhost:11434/v1/chat/completions` (the `openai` client sends paths without `/v1`; Ollama requires it — the proxy adds the prefix). For streamed requests, `stream_options: {"include_usage": true}` is injected so Ollama reports token counts.
5. **Stream back** — SSE chunks pass through to the client as they arrive; the proxy never buffers the full response.
6. **Record** — the final chunk carries the `usage` object; the proxy writes one `usage_events` row (user, model, prompt/completion tokens, cost from the price table).
7. The user API (`/usage`) and admin APIs (`/admin/...`) are queries over that table; the React UI is a static bundle served by FastAPI, polling those same APIs.

Two load-bearing properties: **all state lives in one SQLite file** (nothing in memory that matters for billing), and **the proxy never interprets model output** — it only reads usage numbers off the end of the response.

## 3. Decisions

<!-- One subsection per decision as they are made: chosen approach, alternatives considered, tradeoffs, why. -->

### 3.1 Language & framework — Python + FastAPI

The workload is almost entirely concurrent I/O passthrough (accept, forward, stream back), which fits an async-native framework. FastAPI over Django: Django's async support is retrofitted (sync ORM, awkward ASGI streaming) and its ORM/admin machinery adds unused weight. Over Go/TypeScript: author fluency wins for a system that must be defended line-by-line.

### 3.2 Upstream client — raw HTTP via httpx (no ollama-python, no `requests`)

The proxy sits between two parties already speaking the same protocol, so its core job is passing bytes through with minimal edits (auth header, `/v1` prefix, `stream_options` injection). `ollama-python` would force a double translation (OpenAI JSON → native Ollama calls → back to OpenAI JSON), adding code and compatibility risk. `requests` is synchronous and would block the event loop under concurrent load; `httpx.AsyncClient` streams chunk-by-chunk and pools connections.

### 3.3 Storage — SQLite (WAL mode)

Billing data must survive a restart, ruling out in-memory-only. A single-process proxy makes an embedded DB the simplest durable option: queries are in-process function calls (no network hop, no pool), and WAL mode lets readers proceed while one writer inserts usage rows — hundreds of small inserts/sec is comfortably in range. The tradeoff: SQLite is single-writer, single-machine. The moment this scales to multiple proxy instances, usage state must move to a shared store (Postgres/Redis); the storage layer is kept narrow so that swap is contained.

### 3.4 Frontend — React + TypeScript + Vite, built to static files

Vite builds the admin/usage UI to a static `dist/` that FastAPI serves — at runtime there is still exactly one server, no CORS, no extra hop (the problems that ruled out Next.js). React over a hand-rolled static page: author fluency, and the dashboard's live-polling state fits React's model. Build artifacts are not committed; the README documents the build.

### 3.5 Billing & limits

**Three limit types, one concern each.** Short-term = **requests/minute** (protects infrastructure from bursts; needs no token counts). Long-term = **tokens/day** (caps spend velocity — a user can't quietly burn a large budget in a day even at low RPM). Total = **lifetime spend cap in dollars** (absolute exposure, in the same currency the bill is in). Alternative considered: OpenAI-style RPM+TPM both in the short window — more faithful to real providers, but two short-window checks blur the "three distinct types" the requirement asks for.

**Sliding windows, computed by SQL.** A rate check is `SELECT SUM(...) FROM usage_events WHERE user = ? AND ts > now - <window>` compared to the limit. Since the usage table must exist for billing anyway, the rate limiter is a query, not a data structure — simpler *and* more accurate than a fixed window (which permits 2× bursts at boundaries). A token bucket (bucket of permits refilling at a constant rate; empty bucket → reject) gives smoother behavior and O(1) checks, but requires live per-user counters — a second source of truth. At multi-instance scale the SQL scan flips to exactly that: token buckets in Redis; here, indexed SQLite queries over small windows are microseconds.

**Optimistic enforcement (check-before, record-after).** A request's token cost is only known after it completes, so each request is admitted based on *recorded* usage: over any limit → 429 before forwarding; otherwise forward, then record. A user at their cap can overshoot by at most the cost of their in-flight requests — acceptable for in-arrears billing (the same tradeoff real providers make). Rejected alternatives: pre-flight estimation/reservation (much more code, still imprecise) and mid-stream aborts (hostile UX, saves pennies). This also settles race handling: concurrent requests near a boundary cause bounded overshoot, not corruption, so no locking is added to prevent what the billing model already tolerates.

**Price sheet: hardcoded config, not data.** Per-model input/output prices ($/1M tokens), anchored to real market rates for comparable small models. A price sheet is provider configuration that changes by deploy, not runtime data — keeping it in code avoids admin endpoints, UI, and price-audit questions. **Unknown models are rejected** with OpenAI's `model_not_found` error: never proxy what you can't bill.

**Errors mirror OpenAI exactly.** HTTP 429 for all three limit types with the standard error body: `rate_limit_exceeded` (+ `Retry-After`) for the windowed limits, `insufficient_quota` for the spend cap — so the `openai` SDK raises its native `RateLimitError` with no client changes. 402 for the spend cap would be purer HTTP but diverges from the API this proxy claims compatibility with.

**Conservative defaults; admin overrides.** New users start at 60 RPM, 1M tokens/day, $5.00 lifetime — production-minded (a new user can't silently run up spend) rather than unlimited-until-configured. Admins set or clear each limit independently. Rejected (429'd) requests are not recorded, so they don't count toward the RPM window — retrying while blocked doesn't extend the block, and one table drives billing, limits, and usage APIs alike.

<!-- Upcoming: proxy surface & auth, concurrency & load demo, admin UI scope. -->
