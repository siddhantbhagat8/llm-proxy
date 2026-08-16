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

### 3.6 Proxy surface & auth

**Whitelist, not catch-all.** The proxy forwards exactly one endpoint: `POST /chat/completions` (accepted with or without the `/v1` prefix, since the `openai` client's path depends on how `base_url` is written; Ollama requires `/v1`, so the proxy normalizes). A transparent catch-all would be more "proxy-like" but would forward traffic our usage recording can't parse — embeddings and legacy completions consume tokens too. Same principle as unknown models: never proxy what you can't bill. Adding an endpoint later = one route + one usage extractor.

**`GET /models` is served from the price sheet, not forwarded.** Ollama would list everything installed locally, including models with no price. The proxy's contract is "models you may use and be billed for" — serving the list from the price sheet means the model list and the unknown-model rejection can never disagree.

**API keys: `sk-proxy-<32 hex>`, stored in plaintext — deliberately.** The `sk-` convention makes keys look native in OpenAI clients and grep-able in logs. Keys are stored as-is in `users.token`, so an operator can read any user's key straight from the DB or the admin API — the right convenience for a local demo system whose DB never leaves the machine (no key-copying ceremony between demo steps). This is intentionally *not* the production answer: real providers store only a SHA-256 hash and show the plaintext exactly once at creation, so a DB leak doesn't leak credentials. The swap back is contained — hash on insert, hash on lookup, drop the key from admin responses — and lookup is an indexed equality either way.

**Admin = `is_admin` flag, one auth scheme everywhere.** Every request — chat, usage, admin — authenticates the same way: `Authorization: Bearer <token>` → hash lookup → user row; `/admin/*` routes additionally require `is_admin`. Alternative considered: a static operator key in an env var, which keeps the admin credential out of the DB but forces a second auth path and a separate "admin key" concept in the UI. The flag wins: unified auth code, natural extension to roles, and the bootstrap problem (first admin must exist) is solved by seeding.

**Routes** — the OpenAI-compatible namespace stays pristine; everything of ours lives beside it:

```
POST /chat/completions, /v1/chat/completions    proxied            (user token)
GET  /models, /v1/models                        from price sheet   (user token)
GET  /usage                                     own usage + limit standing (user token)
GET  /admin/users                               list users w/ usage + limits (admin)
POST /admin/users                               create user → API key returned (admin)
PUT  /admin/users/{id}/limits                   set/clear limits   (admin)
GET  /healthz                                   liveness, unauthenticated
GET  /                                          dashboard (frontend/dist)
```

**Provisioning: CLI script, not startup seeding.** `uv run python -m scripts.create_user <name> [--admin]` writes directly to the DB and prints the key — which is also how the first admin gets created (the admin API itself requires an admin, so bootstrap can't go through HTTP). Startup seeding of fixed demo accounts was the earlier approach and was replaced: explicit creation keeps the DB free of magic accounts, and plaintext-at-rest already removes the token-copying friction seeding existed to solve. Auth failures mirror OpenAI exactly: 401 `invalid_api_key`, and OpenAI-shaped 403 for non-admins on admin routes.

### 3.7 Concurrency & the load demo

**The requirement's two phrases are two different properties.** "Handle lots of concurrent users" is about **concurrency** — how many requests are *in flight* at once. "Demonstrate hundreds of requests per second" is about **throughput** — and completions/sec is a property of the *model server*, not the proxy: a 1B model on a laptop tops out at tens of completions/sec no matter how the proxy is written. In production this proxy fronts providers with effectively unlimited capacity, where the real question is whether *the proxy's* pipeline (auth → limit check → forward → record) sustains hundreds of rps. One-liner: *completions/sec is the provider's number; requests/sec is mine.* So the demo has two scenarios:

1. **Concurrency, real LLM**: 200+ users streaming through the proxy from Ollama (`OLLAMA_NUM_PARALLEL=4`). Four requests decode at a time; the rest wait in Ollama's internal FIFO queue (512-deep, then 503 — passed through honestly), their connections held open, the wait surfacing as time-to-first-token. Proves the proxy holds hundreds of open SSE streams with stable memory while auth, limits, and the dashboard stay responsive. (`NUM_PARALLEL` has no hard cap, but slots share compute and each costs KV-cache memory — 4–8 is the practical ceiling here; it reshapes the queue, it doesn't add horsepower.)
2. **Throughput, provider-grade upstream**: `oha` drives ≥500 rps through the *byte-identical* proxy against a stub upstream that plays OpenAI — a standalone script returning a canned OpenAI-shaped response (with a `usage` object, so billing still exercises) at ~50ms simulated provider latency. The stub lives **outside** the proxy (`load/`), reached via the same upstream-URL config: zero test scaffolding in the tested binary. Measuring only against real Ollama was rejected — "20 rps" describes the model, not the proxy, and any server survives 20 rps.

**Configuration**: a single uvicorn process (async I/O covers hundreds of concurrent requests when per-request work is microseconds of SQL; one process keeps SQLite's single-writer story clean), with the httpx connection-pool limit raised above its default 100 so the proxy doesn't self-throttle. `--workers N` is the documented first scale knob — after measuring, not before. **Recorded metrics**: sustained rps, p50/p95/p99 latency for both scenarios, and the proxy's added overhead (stub-direct vs through-proxy).

**Why no request queue in the proxy** (a suggested bonus feature): upstream queueing already exists — Ollama queues beyond its parallel slots exactly as real providers queue and rate-limit internally. A proxy-side queue would double-queue every request: added latency and a second tuning surface, no added protection.

### 3.8 Dashboard (bonus feature)

**One page; the API key decides the view.** The dashboard authenticates exactly like the API — paste a key, it's sent as `Authorization: Bearer` on every poll. An admin key unlocks the fleet view; a user key shows that user's own usage. No separate admin app, no client-side routing, no second auth concept.

```
admin view                                          user view
──────────────────────────────────────────          ─────────────────────────
3 users · 1,204 requests · $1.87 spend  ⟳2s         alice — your usage
name   key         req/min    tokens/day   spend    [▓▓▓░ 34/60] [▓░ 88k/1M] [▓▓ $0.42/$5]
alice  sk-… [copy] ▓▓▓ 34/60  ▓ 88k/1M  ▓ $0.42/$5  per-model: llama3.2:1b · moondream
  └ per-model breakdown        [edit limits]
bob    sk-… [copy] ▓▓▓▓▓ 60/60! …
+ create user [name] [ ] admin → key shown once
```

**Live limit meters.** The usage summary already returns `requests_last_minute` and `tokens_last_day` — the exact numerators for the three limits — so each renders as a `used / limit` progress meter (red at 100%, ∞ when no limit set). With **2-second polling**, usage visibly ticks during a load run and a rate-limited user's meter pins red live. Polling over websockets: one `setInterval`, and 2s staleness is irrelevant for a billing dashboard.

**Per-model breakdown is first-class**, not decoration: "usage across the different models" is an explicit assignment requirement. Grounding this sketch against the real API surfaced that the summary lacked it — fixed by adding a `GROUP BY model` breakdown to the existing summary payload (no new endpoint; the list and detail views inherit it).

**Components: shadcn/ui.** shadcn is not a component-library dependency — its CLI copies component *source* into the repo (Radix primitives + Tailwind underneath). Visual design is offloaded to proven components while every line remains ours to read and defend — unlike an opaque library (MUI/AntD), and much faster than hand-rolling CSS under a deadline. Cost accepted: Tailwind + a few Radix packages join the pinned deps, plus one-time CLI setup. shadcn's `Progress` is the limit meter.

**Admin table shows plaintext keys with a copy button** — consistent with the deliberate plaintext-at-rest decision (3.6): the operator can grab any user's key mid-demo to switch identities. Under hash-at-rest, this column disappears; the UI would show key prefixes only.

### 3.9 Load demo: measured numbers

All measurements on the development machine (Apple Silicon Mac), `oha` driving `POST /chat/completions` for a provisioned no-limit user; the stub upstream (`load/stub_upstream.py`) simulates a production-capacity provider at 50ms latency. Reproduce with the commands in the README.

| run | rps | p50 | p95 | p99 | success |
|---|---|---|---|---|---|
| stub direct (baseline), c=64 | 1,198 | 53ms | 57ms | 60ms | 100% |
| through proxy, 1 worker, c=64 | 103 | 448ms | 1.53s | 2.44s | 99.6% |
| **through proxy, 8 workers, c=64** | **1,210** | **52ms** | **56ms** | **71ms** | **100%** |
| through proxy, 8 workers, c=256 | 720 | 199ms | 1.13s | 1.85s | 98.8% |

The 8-worker run is statistically indistinguishable from hitting the stub directly — **the proxy's added latency is sub-millisecond** at the sustained plateau, and 1,210 rps clears the "hundreds of requests per second" bar with the full pipeline (auth → three limit checks → forward → usage recording) on every request. c=256 is past the sweet spot (queueing tails); c=64–128 is the honest sustained figure.

**Billing integrity under load**: on a fresh database, recorded `usage_events` rows matched successful responses exactly — plus a handful of requests that completed upstream just as the load generator hit its deadline and hung up. Those are still billed, which is *correct*: usage records what the provider consumed, not what the client waited around for.

**Measured, then scaled.** A single async process plateaued at ~103 rps — CPU-bound on one core (per-request work: JSON handling, four SQLite statements, httpx client machinery ≈ a few ms), with latency under load being pure queueing. `--workers 8` was the documented scale knob (3.7); turning it produced the 12× jump. Eight processes share the SQLite file safely: WAL + `busy_timeout` + short single-statement writes.

**What load testing actually caught** — two real bugs that functional tests missed, which is the argument for load-testing at all:

1. **Sync auth dependencies ran in FastAPI's threadpool**, so the single SQLite connection was used from many threads concurrently → `InterfaceError`s and corrupted bindings under load. Fix: the dependencies are `async`, which pins every DB call to the event-loop thread — the single-writer design made literal. (Rule recorded in code: anything touching the DB stays async.)
2. **Multi-worker boot raced on a fresh database**: eight processes converting the same new file to WAL and creating the schema simultaneously → `database is locked`, server exit. `busy_timeout` does not fix this one — SQLite fails journal-mode changes *immediately* under contention (deadlock avoidance bypasses the busy handler) — so initialization retries with backoff. Verified with five consecutive fresh-DB 8-worker cold boots.

Tuning that came with this: `synchronous=NORMAL` (WAL-safe; skips fsync-per-commit — at most the last writes are lost on an OS crash, acceptable for usage events) and an httpx pool limit raised above its default 100 connections.

**Concurrency scenario (real Ollama, `OLLAMA_NUM_PARALLEL=4`)**: `load/scenario.py` opened **200 simultaneous streaming requests — all 200 completed, zero failures — held open for 125 seconds** while Ollama's FIFO drained them four at a time. The queue is visible as time-to-first-token: p50 94s, max 118s, connections open throughout. Meanwhile a 3-RPM user fired six requests: exactly 3 succeeded, 3 got live 429s. This is the "lots of concurrent users" half of the requirement with genuine model traffic; the throughput table above is the "hundreds of rps" half.

<!-- Upcoming: demo runbook. -->
