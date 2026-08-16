import os

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
DATABASE_PATH = os.environ.get("DATABASE_PATH", "llm_proxy.db")
FRONTEND_DIST_DIRECTORY = "frontend/dist"

# Dollars per 1M tokens, hypothetical demo-scale prices.
# Provider configuration, not runtime data — changes by deploy (DESIGN.md 3.5).
PRICE_SHEET = {
    "llama3.2:1b": {"input": 500.0, "output": 1000.0},
    "moondream": {"input": 1000.0, "output": 2000.0},
}

DEFAULT_REQUESTS_PER_MINUTE = 5
DEFAULT_TOKENS_PER_DAY = 1_000
DEFAULT_LIFETIME_SPEND_DOLLARS = 5.0
