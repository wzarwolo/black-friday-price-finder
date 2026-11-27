"""Command line: find the lowest price for a product and predict next week's price.

    python -m pricefinder "Daisy Ever So Fresh Eau de Parfum" --brand "Marc Jacobs"
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date

from . import history, matching
from .models import Offer
from .predict import black_friday, cyber_monday, predict
from .sources import google_shopping, product_url, shopify, walmart

SOURCES = {
    "walmart": walmart.search,
    "shopify": shopify.search,
    "google": google_shopping.search,
}


def gather(query: str, brand: str | None, urls: list[str], sources: list[str]) -> tuple[list[Offer], list[str]]:
    search_text = f"{brand} {query}" if brand else query
    offers: list[Offer] = []
    problems: list[str] = []
    for name in sources:
        if name == "google" and not google_shopping.enabled():
            problems.append("Google Shopping skipped (set SERPAPI_KEY to search Amazon, Ulta, Sephora, Macy's, etc.)")
            continue
        try:
            found = SOURCES[name](search_text)
            offers.extend(found)
        except Exception as e:  # one broken site shouldn't stop the others
            problems.append(f"{name}: {e}")
    for url in urls:
        try:
            offers.extend(product_url.fetch(url))
        except Exception as e:
            problems.append(f"{url}: {e}")
    return offers, problems


def filter_offers(offers: list[Offer], query: str, brand: str | None, keep_flags: set[str],
                  from_urls: set[str]) -> list[Offer]:
    kept, seen = [], set()
    for o in offers:
        o.flags = sorted(set(o.flags) | set(matching.detect_flags(o.title)))
        o.size_oz = matching.parse_size_oz(o.title)
        direct = o.url in from_urls  # pasted URLs are trusted to be the right product
        if not direct and not matching.is_match(o.title, query, brand):
            continue
        if not direct and matching.url_contradicts(o.url, query, brand):
            continue
        if set(o.flags) - keep_flags:
            continue
        if o.in_stock is False:
            continue
        key = (o.retailer, o.seller, o.title.lower(), o.price)
        if key in seen:
            continue
        seen.add(key)
        kept.append(o)
    return kept


def money(x: float | None) -> str:
    return f"${x:,.2f}" if x is not None else "-"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Find the lowest price for a product and predict if it will drop this week.")
    ap.add_argument("query", help='product name, e.g. "Daisy Ever So Fresh Eau de Parfum"')
    ap.add_argument("--brand", help='brand, e.g. "Marc Jacobs" (used in search; optional in titles)')
    ap.add_argument("--url", action="append", default=[], help="also check this product page (repeatable)")
    ap.add_argument("--sources", default="walmart,shopify,google", help="comma list: walmart,shopify,google")
    ap.add_argument("--size", type=float, help="only show this size in fl oz, e.g. 2.5")
    ap.add_argument("--msrp", type=float, help="list price, if you know it (improves the prediction)")
    ap.add_argument("--include", default="", help="also include flagged listings: tester,set,mini,variants")
    ap.add_argument("--top", type=int, default=10, help="how many offers to list")
    ap.add_argument("--date", type=date.fromisoformat, help="pretend today is YYYY-MM-DD (for testing)")
    ap.add_argument("--no-save", action="store_true", help="don't record prices in local history")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    today = args.date or date.today()
    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    keep_flags = {f.strip() for f in args.include.split(",") if f.strip()}

    raw, problems = gather(args.query, args.brand, args.url, sources)
    offers = filter_offers(raw, args.query, args.brand, keep_flags, set(args.url))
    if args.size:
        offers = [o for o in offers if o.size_oz and abs(o.size_oz - args.size) < 0.05]
    offers.sort(key=lambda o: o.price)

    if not args.no_save and offers:
        history.save(args.query, offers)

    # Group by size so a 1 oz bottle isn't compared against a 4.2 oz one.
    by_size: dict[float | None, list[Offer]] = defaultdict(list)
    for o in offers:
        by_size[o.size_oz].append(o)

    predictions = {}
    for size, group in by_size.items():
        best = group[0]
        predictions[size] = predict(
            args.query,
            current_price=best.price,
            list_prices=[o.list_price for o in group if o.list_price],
            market_prices=[o.price for o in group],
            today=today,
            msrp=args.msrp if args.size else None,
            daily_lows=history.daily_lows(args.query, size),
        )

    if args.json:
        print(json.dumps({
            "query": args.query, "date": today.isoformat(),
            "offers": [o.to_dict() for o in offers],
            "by_size": {str(size): {"lowest": group[0].to_dict(), "prediction": {
                **predictions[size].__dict__, "expected_low_day": predictions[size].expected_low_day.isoformat()}}
                for size, group in by_size.items()},
            "problems": problems,
        }, indent=2, default=str))
        return 0

    title = f"{args.brand} {args.query}" if args.brand else args.query
    bf, cm = black_friday(today.year), cyber_monday(today.year)
    print(f"\n{title}  ·  {today:%a %b %d, %Y}  (Black Friday {bf:%b %d}, Cyber Monday {cm:%b %d})")
    print(f"Checked {len(raw)} listings, {len(offers)} match.\n")

    if not offers:
        print("No matching offers found. Try a shorter query, --brand, or --url with a product page.")
    else:
        print(f"Lowest prices overall (top {min(args.top, len(offers))}):")
        print(f"  {'Price':>9}  {'$/oz':>7}  {'Size':>7}  {'Where':<34} Link")
        for o in offers[: args.top]:
            where = o.retailer + (f" ({o.seller})" if o.seller and o.seller != o.retailer else "")
            size = f"{o.size_oz:g} oz" if o.size_oz else "?"
            print(f"  {money(o.price):>9}  {money(o.price_per_oz):>7}  {size:>7}  {where[:34]:<34} {o.url}")

        print("\nBest price per size + 7-day forecast:")
        sizes = sorted(by_size, key=lambda s: (s is None, s or 0))
        for size in sizes:
            best, p = by_size[size][0], predictions[size]
            label = f"{size:g} oz" if size else "size ?"
            print(f"  {label:>7}: {money(best.price)} at {best.retailer}"
                  f"  |  {int(p.probability_lower * 100)}% chance lower by {p.expected_low_day_label}"
                  f" (expected low ~{money(p.expected_low)}, {p.confidence} confidence)  ->  {p.recommendation}")
            if p.history_note:
                print(f"           {p.history_note}")

        cheapest_oz = min((o for o in offers if o.price_per_oz), key=lambda o: o.price_per_oz, default=None)
        if cheapest_oz:
            print(f"\nBest value: {cheapest_oz.size_oz:g} oz for {money(cheapest_oz.price)} "
                  f"({money(cheapest_oz.price_per_oz)}/oz) at {cheapest_oz.retailer} -> {cheapest_oz.url}")

    for msg in problems:
        print(f"note: {msg}", file=sys.stderr)
    print("\nForecast uses prior-Black-Friday patterns (pricefinder/trends.json) plus your saved history;"
          " run daily to sharpen it. Not a guarantee.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
