import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.cost import calculate_token_cost_cents


def test_basic_input_cost():
    # 1,000,000 input tokens at 150 cents/million = 150 cents
    cost = calculate_token_cost_cents(1_000_000, 0, 0, 0)
    assert cost == 150


def test_cached_input_cheaper_than_fresh():
    fresh = calculate_token_cost_cents(1_000_000, 0, 0, 0)
    cached = calculate_token_cost_cents(0, 1_000_000, 0, 0)
    assert cached < fresh


def test_reasoning_tokens_billed_as_output():
    # reasoning tokens should cost the same as equivalent output tokens
    output_only = calculate_token_cost_cents(0, 0, 1_000_000, 0)
    reasoning_only = calculate_token_cost_cents(0, 0, 0, 1_000_000)
    assert output_only == reasoning_only


def test_categories_not_simply_summed():
    # 500k input + 500k output should NOT equal treating 1M as one flat category
    mixed = calculate_token_cost_cents(500_000, 0, 500_000, 0)
    all_input = calculate_token_cost_cents(1_000_000, 0, 0, 0)
    assert mixed != all_input


if __name__ == "__main__":
    test_basic_input_cost()
    test_cached_input_cheaper_than_fresh()
    test_reasoning_tokens_billed_as_output()
    test_categories_not_simply_summed()
    print("All cost tests passed.")