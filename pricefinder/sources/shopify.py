"""Any Shopify-powered store (Perfumania and many indie retailers).

Shopify stores expose public JSON endpoints:
  /search/suggest.json  -> product search
  /products/<handle>.js -> every size/variant with its price and compare-at price
"""
from __future__ import annotations

import urllib.parse

from .. import http
from ..models import Offer

# Add more Shopify store domains here (display name -> domain).
STORES = {
    "Perfumania": "perfumania.com",
}


def search_store(name: str, domain: str, query: str, limit: int = 10) -> list[Offer]:
    base = f"https://{domain}"
    params = urllib.parse.urlencode({
        "q": query,
        "resources[type]": "product",
        "resources[limit]": limit,
    })
    results = http.get(f"{base}/search/suggest.json?{params}").json()
    products = results.get("resources", {}).get("results", {}).get("products", [])

    offers: list[Offer] = []
    for p in products:
        handle = p.get("handle") or p["url"].split("/products/")[1].split("?")[0]
        try:
            product = http.get(f"{base}/products/{handle}.js").json()
        except Exception:
            continue
        for v in product.get("variants", []):
            variant_title = v.get("title") or ""
            title = product["title"] if variant_title == "Default Title" else f"{product['title']} - {variant_title}"
            compare = v.get("compare_at_price")
            offers.append(Offer(
                retailer=name,
                title=title,
                price=v["price"] / 100,
                list_price=(compare / 100) if compare and compare > v["price"] else None,
                url=f"{base}/products/{handle}?variant={v['id']}",
                in_stock=v.get("available"),
            ))
    return offers


def search(query: str) -> list[Offer]:
    offers: list[Offer] = []
    for name, domain in STORES.items():
        offers.extend(search_store(name, domain, query))
    return offers
