from __future__ import annotations

import re

_AMOUNT = re.compile(r"\$\s?(\d+(?:\.\d{1,2})?)")
_FREE = re.compile(r"\bfree\b(?!\s+(?:with|for)\s+purchase)", re.IGNORECASE)
_FEES = re.compile(r"\+\s*\$\s?\d+(?:\.\d{1,2})?\s*(?:booking|service|handling|processing|ticketing)?\s*fees?", re.I)
# Phrases that mean the event itself is free (as opposed to "free food" or "free t-shirts").
_FREE_EVENT = re.compile(
    r"free (?:and open to the public|admission|of charge|event|entry|to attend|for (?:all|students|everyone|the umd)|"
    r"with (?:a |your )?(?:valid )?(?:umd|uid|student))|admission is free|no cost to attend|tickets are free|"
    r"\bno charge\b",
    re.I,
)


def parse_price(text: str | None) -> tuple[float | None, float | None, bool | None]:
    """Return (price_min, price_max, is_free) from free text like '$20/$30', 'Free', '$4 – $6'."""
    if not text:
        return None, None, None
    text = _FEES.sub(" ", text)
    amounts = [float(a) for a in _AMOUNT.findall(text.replace(",", ""))]
    amounts = [a for a in amounts if a < 10000]
    free = bool(_FREE.search(text))
    if amounts:
        low, high = min(amounts), max(amounts)
        if free:  # e.g. "Free for students, $20 general admission"
            low = 0.0
        return low, high, high == 0
    if free:
        return 0.0, 0.0, True
    return None, None, None


def mentions_free_admission(text: str | None) -> bool:
    return bool(text and _FREE_EVENT.search(text))


def format_price(price_min: float | None, price_max: float | None, is_free: bool | None) -> str | None:
    if is_free:
        return "Free"
    if price_min is None and price_max is None:
        return None
    low, high = price_min or 0, price_max if price_max is not None else price_min
    fmt = lambda v: f"${v:,.0f}" if float(v).is_integer() else f"${v:,.2f}"  # noqa: E731
    if low == 0 and high:
        return f"Free–{fmt(high)}"
    if high is None or low == high:
        return fmt(low)
    return f"{fmt(low)}–{fmt(high)}"
