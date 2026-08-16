"""The concurrency story (DESIGN.md 3.7, scenario 1): many users, real Ollama.

Opens one streaming chat completion per user, all at once. Ollama decodes
OLLAMA_NUM_PARALLEL at a time and queues the rest internally, so the wait
shows up as time-to-first-token — what this measures per user. Meanwhile one
rate-limited user ("limited-larry", 3 RPM) fires six requests to show live
429s. Watch the dashboard while it runs.

Run from the repo root: uv run -m load.scenario [--users 200] [--proxy URL]
"""

import argparse
import asyncio
import json
import time

import httpx

from app import config, database
from app.services.user_service import UserService
from load.provision import ensure_user

UNLIMITED = {
    "requests_per_minute": None,
    "tokens_per_day": None,
    "lifetime_spend_dollars": None,
}


def provision(count: int) -> tuple[list[str], str]:
    connection = database.connect(config.DATABASE_PATH)
    try:
        user_service = UserService(connection)
        tokens = [
            ensure_user(user_service, f"load-{index:03d}", UNLIMITED).token
            for index in range(count)
        ]
        larry = ensure_user(
            user_service, "limited-larry", {**UNLIMITED, "requests_per_minute": 3}
        )
        return tokens, larry.token
    finally:
        connection.close()


async def stream_one(client: httpx.AsyncClient, token: str) -> tuple[float, float]:
    """Returns (time to first token, total time) for one streamed completion."""
    started = time.monotonic()
    first_token_at = None
    async with client.stream(
        "POST",
        "/chat/completions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "model": "llama3.2:1b",
            "messages": [{"role": "user", "content": "One fun fact, briefly."}],
            "max_tokens": 24,
            "stream": True,
        },
    ) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if (
                first_token_at is None
                and line.startswith("data: {")
                and json.loads(line[6:])["choices"]
            ):
                first_token_at = time.monotonic()
    return (first_token_at or time.monotonic()) - started, time.monotonic() - started


async def hammer_larry(client: httpx.AsyncClient, token: str) -> tuple[int, int, int]:
    """Six quick non-streamed requests against a 3 RPM limit: expect ~3 OK, ~3 429."""
    ok = throttled = errors = 0
    for _ in range(6):
        try:
            response = await client.post(
                "/chat/completions",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "model": "llama3.2:1b",
                    "messages": [{"role": "user", "content": "Hi."}],
                    "max_tokens": 4,
                },
            )
        except httpx.HTTPError:
            errors += 1
            continue
        ok, throttled = ok + (response.status_code == 200), throttled + (
            response.status_code == 429
        )
    return ok, throttled, errors


def percentile(values: list[float], fraction: float) -> float:
    return sorted(values)[min(int(len(values) * fraction), len(values) - 1)]


async def run(proxy_url: str, user_count: int) -> None:
    tokens, larry_token = provision(user_count)
    print(f"{user_count} users provisioned; opening all streams at once...")
    async with httpx.AsyncClient(
        base_url=proxy_url,
        timeout=httpx.Timeout(5, read=600),
        limits=httpx.Limits(max_connections=user_count + 10),
    ) as client:
        started = time.monotonic()
        results, (larry_ok, larry_429, larry_errors) = await asyncio.gather(
            asyncio.gather(
                *(stream_one(client, token) for token in tokens),
                return_exceptions=True,
            ),
            hammer_larry(client, larry_token),
        )
        wall = time.monotonic() - started

    completed = [result for result in results if isinstance(result, tuple)]
    failed = len(results) - len(completed)
    first_token_times = [ttft for ttft, _ in completed]
    print(f"\nconcurrent streams held: {user_count}   wall time: {wall:.1f}s")
    print(f"completed: {len(completed)}   failed: {failed}")
    if first_token_times:
        print(
            "time to first token   "
            f"p50 {percentile(first_token_times, 0.50):.1f}s   "
            f"p95 {percentile(first_token_times, 0.95):.1f}s   "
            f"max {max(first_token_times):.1f}s"
        )
    larry_note = f" ({larry_errors} connection errors)" if larry_errors else ""
    print(f"limited-larry (3 RPM): {larry_ok} ok, {larry_429} rate-limited{larry_note}")
    if failed or larry_errors:
        print(
            "\nconnection failures usually mean a file-descriptor limit: this "
            "scenario needs ~2x --users sockets on the proxy and ~1x here — run "
            "`ulimit -n 4096` in BOTH terminals and retry."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Concurrency scenario vs real Ollama.")
    parser.add_argument("--users", type=int, default=200)
    parser.add_argument("--proxy", default="http://localhost:8000")
    args = parser.parse_args()
    asyncio.run(run(args.proxy, args.users))


if __name__ == "__main__":
    main()
