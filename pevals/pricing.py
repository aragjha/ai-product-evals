"""List prices in USD per million tokens, checked 2026-10. Update when prices change."""
from __future__ import annotations

PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
}


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    key = next((k for k in PRICES if model.startswith(k)), None)
    if key is None:
        return 0.0  # unknown model: reported as 0 and flagged in the report
    p_in, p_out = PRICES[key]
    return round(input_tokens * p_in / 1e6 + output_tokens * p_out / 1e6, 6)


def known(model: str) -> bool:
    return any(model.startswith(k) for k in PRICES)
