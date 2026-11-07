"""
Prices per million tokens for the models the evals call, and the dollar cost of one call.

Prices change: re-check them on the providers' pricing pages before quoting a cost.
"""


# Constants
## US dollars per million tokens, input and output
PRICE_PER_MILLION_TOKENS = {
    # Mistral's model card, checked 1 Nov 2026
    "mistral-large-4-0": {"input": 0.70, "output": 2.10},
    # Anthropic's pricing page, checked 7 Nov 2026
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00},
}


# ===== Cost of one call =====

def call_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Returns the cost of one call in US dollars."""
    prices = PRICE_PER_MILLION_TOKENS[model]
    input_cost = input_tokens * prices["input"] / 1_000_000
    output_cost = output_tokens * prices["output"] / 1_000_000
    return input_cost + output_cost
