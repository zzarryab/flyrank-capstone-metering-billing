PLANS = {
    "free": {
        "api_calls_limit": 1000,
        "ai_tokens_limit": 100_000,
        "price_cents": 0,
    },
    "pro": {
        "api_calls_limit": 50_000,
        "ai_tokens_limit": 5_000_000,
        "price_cents": 2900,  # $29.00 — always store money as integer cents
    },
}

# Simulated token pricing (per 1M tokens, in cents) — pinned constants
TOKEN_PRICING_CENTS_PER_MILLION = {
    "input": 150,          # $1.50 / 1M input tokens
    "cached_input": 37,    # cached input is cheaper
    "output": 600,         # $6.00 / 1M output tokens
    # reasoning tokens are billed at the OUTPUT rate, never a separate category
}