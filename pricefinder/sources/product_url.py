"""Read the price from any product page URL you paste in.

Most retailers publish schema.org Product data (JSON-LD) for Google; we read that.
Sites with heavy bot protection (Amazon, Nordstrom Rack, Macy's) may refuse.
"""
from __future__ import annotations

import json
import urllib.parse

from bs4 import BeautifulSoup

from .. import http
from ..models import Offer


def _walk(node):
    if isinstance(node, list):
        for n in node:
            yield from _walk(n)
    elif isinstance(node, dict):
        yield node
        for key in ("@graph", "hasVariant", "offers", "itemListElement"):
            if key in node:
                yield from _walk(node[key])


def _is(node: dict, kind: str) -> bool:
    t = node.get("@type")
    return t == kind or (isinstance(t, list) and kind in t)


def fetch(url: str) -> list[Offer]:
    html = http.get(url).text
    soup = BeautifulSoup(html, "html.parser")
    retailer = urllib.parse.urlparse(url).netloc.removeprefix("www.")
    offers: list[Offer] = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except json.JSONDecodeError:
            continue
        for node in _walk(data):
            if not _is(node, "Product"):
                continue
            name = node.get("name", "")
            raw_offers = node.get("offers") or []
            for o in _walk(raw_offers):
                if not (_is(o, "Offer") or _is(o, "AggregateOffer")):
                    continue
                price = o.get("price") or o.get("lowPrice")
                if price in (None, ""):
                    continue
                offers.append(Offer(
                    retailer=retailer,
                    title=o.get("name") or name,
                    price=float(price),
                    list_price=float(o["highPrice"]) if o.get("highPrice") and _is(o, "AggregateOffer") else None,
                    url=o.get("url") or url,
                    in_stock=("InStock" in str(o.get("availability"))) if o.get("availability") else None,
                ))
    if not offers:
        meta = soup.find("meta", property="product:price:amount") or soup.find("meta", itemprop="price")
        if meta and meta.get("content"):
            title = soup.title.string.strip() if soup.title and soup.title.string else url
            offers.append(Offer(retailer=retailer, title=title, price=float(meta["content"]), url=url))
    return offers
