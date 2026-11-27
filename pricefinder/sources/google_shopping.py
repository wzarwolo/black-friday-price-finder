"""Google Shopping via SerpAPI (optional, covers the whole web: Amazon, Ulta, Sephora,
Macy's, Nordstrom Rack, Target...).

Google Shopping can't be scraped directly (prices load with JavaScript and it blocks
bots), so this uses SerpAPI's official API. Free tier: 100 searches/month.
Get a key at https://serpapi.com and run:  export SERPAPI_KEY=your_key
"""
from __future__ import annotations

import os

from .. import http
from ..models import Offer

NAME = "Google Shopping"


def enabled() -> bool:
    return bool(os.environ.get("SERPAPI_KEY"))


def search(query: str) -> list[Offer]:
    key = os.environ.get("SERPAPI_KEY")
    if not key:
        return []
    resp = http.get("https://serpapi.com/search.json", params={
        "engine": "google_shopping", "q": query, "gl": "us", "hl": "en", "api_key": key,
    })
    offers = []
    for r in resp.json().get("shopping_results", []):
        price = r.get("extracted_price")
        if not price:
            continue
        offers.append(Offer(
            retailer=r.get("source") or NAME,
            title=r.get("title", ""),
            price=float(price),
            list_price=r.get("extracted_old_price"),
            url=r.get("product_link") or r.get("link") or "",
        ))
    return offers
