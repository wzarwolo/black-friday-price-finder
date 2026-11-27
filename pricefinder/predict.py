"""Will the price drop further in the next 7 days?

Model (deliberately simple and transparent):

1. Work out where today sits in the Black Friday season (days from Black Friday).
2. From prior-season patterns (trends.json), get how deep discounts usually get on
   the remaining days of the next week, versus today.
3. Estimate the product's "street price" (usual non-sale price) from MSRP / was-prices
   or from what sellers charge right now, and from that the expected best price in the
   next week.
4. Compare with today's lowest price -> probability it goes lower.
5. If you've run the tool on earlier days, nudge the probability with the real trend
   seen in your local price history.
"""
from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

TRENDS = json.loads((Path(__file__).parent / "trends.json").read_text())["categories"]
WINDOW_DAYS = 7


def thanksgiving(year: int) -> date:
    nov1 = date(year, 11, 1)
    first_thursday = nov1 + timedelta(days=(3 - nov1.weekday()) % 7)
    return first_thursday + timedelta(weeks=3)


def black_friday(year: int) -> date:
    return thanksgiving(year) + timedelta(days=1)


def cyber_monday(year: int) -> date:
    return thanksgiving(year) + timedelta(days=4)


def season_offset(day: date) -> int:
    """Days from the nearest Black Friday (negative = before it)."""
    candidates = [black_friday(day.year - 1), black_friday(day.year), black_friday(day.year + 1)]
    bf = min(candidates, key=lambda b: abs((day - b).days))
    return (day - bf).days


def detect_category(query: str) -> str:
    q = query.lower()
    for name, cfg in TRENDS.items():
        if any(k in q for k in cfg["keywords"]):
            return name
    return "general"


def intensity(category: str, offset: int) -> float:
    """Discount intensity (0..1) on a given day relative to Black Friday, interpolated."""
    curve = sorted((int(k), v) for k, v in TRENDS[category]["curve"].items())
    if offset <= curve[0][0]:
        return curve[0][1]
    if offset >= curve[-1][0]:
        return curve[-1][1]
    for (x0, y0), (x1, y1) in zip(curve, curve[1:]):
        if x0 <= offset <= x1:
            return y0 + (y1 - y0) * (offset - x0) / (x1 - x0)
    return curve[-1][1]


def _label(day: date) -> str:
    y = day.year
    named = {
        thanksgiving(y): "Thanksgiving",
        black_friday(y): "Black Friday",
        black_friday(y) + timedelta(days=1): "Small Business Saturday",
        cyber_monday(y): "Cyber Monday",
    }
    return named.get(day, day.strftime("%a"))


@dataclass
class Prediction:
    category: str
    current_price: float
    street_price: float
    expected_low: float
    expected_low_day: date
    probability_lower: float
    history_note: Optional[str]
    recommendation: str
    confidence: str

    @property
    def expected_low_day_label(self) -> str:
        return f"{_label(self.expected_low_day)} {self.expected_low_day:%b %d}"


def _history_trend(daily_lows: list[tuple[str, float]]) -> tuple[float, Optional[str]]:
    """Return (probability nudge, explanation) from your own saved price history."""
    if len(daily_lows) < 2:
        return 0.0, None
    prices = [p for _, p in daily_lows]
    xs = list(range(len(prices)))
    mean_x, mean_y = statistics.mean(xs), statistics.mean(prices)
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, prices)) / sum((x - mean_x) ** 2 for x in xs)
    pct_per_day = slope / mean_y
    note = f"your history: {len(prices)} days tracked, lowest seen ${min(prices):.2f}"
    if pct_per_day < -0.01:
        return 0.10, note + f", falling ~{abs(pct_per_day) * 100:.1f}%/day"
    if pct_per_day > 0.01:
        return -0.10, note + f", rising ~{pct_per_day * 100:.1f}%/day"
    return 0.0, note + ", flat"


def predict(
    query: str,
    current_price: float,
    list_prices: list[float],
    market_prices: list[float],
    today: Optional[date] = None,
    msrp: Optional[float] = None,
    daily_lows: Optional[list[tuple[str, float]]] = None,
    category: Optional[str] = None,
) -> Prediction:
    today = today or date.today()
    category = category or detect_category(query)
    cfg = TRENDS[category]
    everyday, extra = cfg["everyday_discount"], cfg["peak_extra_discount"]

    offset = season_offset(today)
    today_int = intensity(category, offset)
    upcoming = [(today + timedelta(days=d), intensity(category, offset + d)) for d in range(1, WINDOW_DAYS + 1)]
    best_day, best_int = max(upcoming, key=lambda t: t[1])

    # Usual street (non-sale) price for this product/size.
    # Today's market prices already include today's sale discount; back it out.
    market_street = statistics.median(market_prices) / (1 - extra * today_int)
    list_price = msrp or (max(list_prices) if list_prices else None)
    if msrp:
        street = msrp * (1 - everyday)
    elif list_price:
        # Sellers' "was" prices are unreliable (sometimes inflated, sometimes just their
        # own old price), so never assume a street price below what the market charges.
        street = max(list_price * (1 - everyday), market_street)
    else:
        street = market_street

    expected_low = street * (1 - extra * best_int)
    # How far today's price is above the expected best price, relative to today's price.
    gap = (current_price - expected_low) / current_price
    # Extra lift if the season ahead is more intense than today (prices tend to keep moving).
    momentum = max(0.0, best_int - today_int) * 0.5
    prob = 1 / (1 + math.exp(-(gap / 0.05 + momentum * 4 - 0.5)))

    nudge, history_note = _history_trend(daily_lows or [])
    days_tracked = len(daily_lows or [])
    if days_tracked >= 3:
        confidence, lo, hi = "high", 0.03, 0.97
    elif list_price or len(market_prices) >= 3:
        confidence, lo, hi = "medium", 0.05, 0.9
    else:  # one seller, no list price: we're mostly guessing from the season pattern
        confidence, lo, hi = "low", 0.15, 0.8
    prob = min(hi, max(lo, prob + nudge))

    if prob >= 0.6:
        rec = f"WAIT - likely to drop, best odds around {_label(best_day)}"
    elif prob >= 0.4:
        rec = "TOSS-UP - buy if you're happy at this price, or re-check tomorrow"
    else:
        rec = "BUY - unlikely to get meaningfully cheaper this week"

    return Prediction(
        category=category,
        current_price=current_price,
        street_price=round(street, 2),
        expected_low=round(min(expected_low, current_price), 2),
        expected_low_day=best_day,
        probability_lower=round(prob, 2),
        history_note=history_note,
        recommendation=rec,
        confidence=confidence,
    )
