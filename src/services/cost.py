from src.plans import TOKEN_PRICING_CENTS_PER_MILLION


def calculate_token_cost_cents(input_tokens: int, cached_input_tokens: int, output_tokens: int, reasoning_tokens: int) -> int:
    """
    Real-world AI token pricing rules, encoded:
    - cached input tokens are cheaper than fresh input tokens
    - reasoning tokens are billed at the OUTPUT rate (not a separate category)
    - categories are priced separately, never just added together as one blob
    Returns total cost in integer cents.
    """
    input_cost = (input_tokens / 1_000_000) * TOKEN_PRICING_CENTS_PER_MILLION["input"]
    cached_cost = (cached_input_tokens / 1_000_000) * TOKEN_PRICING_CENTS_PER_MILLION["cached_input"]
    output_cost = ((output_tokens + reasoning_tokens) / 1_000_000) * TOKEN_PRICING_CENTS_PER_MILLION["output"]

    total_cents = input_cost + cached_cost + output_cost
    return round(total_cents)


def calculate_api_call_cost_cents(call_count: int, plan: str) -> int:
    """API calls beyond plan limits are $0 in core scope (overage billing is a stretch goal)."""
    return 0