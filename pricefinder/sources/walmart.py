"""Walmart.com search (includes third-party marketplace sellers).

Walmart is a Next.js site: the search page embeds its results as JSON in a
<script id="__NEXT_DATA__"> tag, so no browser is needed.
"""
from __future__ import annotations

import json
import re
import urllib.parse

from .. import http
from ..models import Offer

NAME = "Walmart"


def _price_lines(item: dict) -> dict:
    out = {}
    details = (item.get("priceInfo") or {}).get("priceDetails") or {}
    for line in details.get("priceLines") or []:
        for v in line.get("values") or []:
            out[v.get("key")] = v.get("value")
    return out


def _to_float(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace("$", "").replace(",", ""))
    except ValueError:
        return None


def search(query: str, max_results: int = 40) -> list[Offer]:
    url = "https://www.walmart.com/search?q=" + urllib.parse.quote(query)
    html = http.get(url).text
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise http.BlockedError("Walmart page had no embedded results (likely a bot check)")
    data = json.loads(m.group(1))
    stacks = data["props"]["pageProps"]["initialData"]["searchResult"]["itemStacks"]

    offers: list[Offer] = []
    for stack in stacks:
        for item in stack.get("items") or []:
            if item.get("__typename") != "Product" or not item.get("name"):
                continue
            lines = _price_lines(item)
            price = _to_float(lines.get("PRICE")) or _to_float(item.get("price"))
            if not price:
                continue
            status = (item.get("availabilityStatusV2") or {}).get("value")
            # Multi-size listings show the cheapest option's price (often a sample vial),
            # so we can't tell which size that price belongs to.
            flags = ["variants"] if item.get("classType") == "VARIANT" or \
                (item.get("priceInfo") or {}).get("priceRangeString") else []
            offers.append(Offer(
                flags=flags,
                retailer=NAME,
                title=item["name"],
                price=price,
                list_price=_to_float(lines.get("WAS_PRICE")),
                url="https://www.walmart.com" + (item.get("canonicalUrl") or "").split("?")[0],
                seller=item.get("sellerName"),
                in_stock=(status == "IN_STOCK") if status else None,
            ))
            if len(offers) >= max_results:
                return offers
    return offers
