# Black Friday Price Finder

Type in a product and this tool finds the lowest prices it can across the web, groups
them by size, and predicts whether the price is likely to drop further in the next
7 days, based on how prices moved around prior Black Fridays.

```
$ python -m pricefinder "Daisy Ever So Fresh Eau de Parfum" --brand "Marc Jacobs"

Marc Jacobs Daisy Ever So Fresh Eau de Parfum  ·  Thu Nov 26, 2026  (Black Friday Nov 27, Cyber Monday Nov 30)
Checked 61 listings, 6 match.

Lowest prices overall (top 6):
      Price     $/oz     Size  Where                              Link
     $19.99   $60.58  0.33 oz  Walmart (Perfume Depot)            https://www.walmart.com/ip/...
     $40.00   $40.00     1 oz  Walmart (BSLLC USA)                https://www.walmart.com/ip/...
     $59.99   $24.00   2.5 oz  Walmart (Milton Elms Industries)   https://www.walmart.com/ip/...
     $68.99   $16.43   4.2 oz  Walmart (Perfume Depot)            https://www.walmart.com/ip/...
    $151.95   $36.18   4.2 oz  Perfumania                         https://perfumania.com/products/...

Best price per size + 7-day forecast:
   4.2 oz: $68.99 at Walmart  |  5% chance lower by Black Friday Nov 27 (...)  ->  BUY - unlikely to get meaningfully cheaper this week
```

## Setup

```bash
cd black-friday-price-finder
python3 -m pip install -r requirements.txt
```

## Usage

```bash
# Search
python3 -m pricefinder "Daisy Ever So Fresh Eau de Parfum" --brand "Marc Jacobs"

# Only one size, with a known MSRP (sharper forecast)
python3 -m pricefinder "Daisy Ever So Fresh Eau de Parfum" --brand "Marc Jacobs" --size 4.2 --msrp 163

# Also check specific product pages (any site that publishes schema.org product data)
python3 -m pricefinder "Daisy Ever So Fresh" --brand "Marc Jacobs" --url "https://www.ulta.com/p/..."

# Include testers / gift sets / minis / multi-size listings (excluded by default)
python3 -m pricefinder "Daisy Ever So Fresh" --include tester,set

# JSON output, or pretend it's a different day
python3 -m pricefinder "Daisy Ever So Fresh" --json
python3 -m pricefinder "Daisy Ever So Fresh" --date 2026-11-20
```

## Where prices come from

| Source | How | Notes |
|---|---|---|
| Walmart.com | Embedded search JSON | Includes many marketplace sellers. |
| Shopify stores (Perfumania by default) | Public `/search/suggest.json` + `/products/<handle>.js` | Add more stores in `pricefinder/sources/shopify.py`. |
| Google Shopping (optional) | [SerpAPI](https://serpapi.com) | Covers Amazon, Ulta, Sephora, Macy's, Nordstrom Rack, Target and others. Free tier is 100 searches/month: `export SERPAPI_KEY=...` |
| Any product URL (`--url`) | schema.org JSON-LD on the page | Sites with heavy bot protection may refuse. |

Amazon, Macy's, eBay, FragranceX and Nordstrom Rack block plain scripted requests, and
Google/Bing Shopping load prices with JavaScript. That's why the Google Shopping API is
the way to reach them.

Listings are filtered so you only compare the real product:
- Every distinctive word of your query must be in the title ("Daisy Eau So Fresh" is
  not "Daisy Ever So Fresh").
- EDP vs EDT must not contradict the query.
- Listings whose URL describes a different product than their title are dropped.
- Testers, gift sets, minis, out-of-stock items and multi-size listings are excluded unless you `--include` them.
- Results are grouped by size, with price per oz.

## How the prediction works

`pricefinder/predict.py`, with priors in `pricefinder/trends.json`:

1. **Season position.** Computes Thanksgiving, Black Friday and Cyber Monday for the
   year and where today falls relative to them.
2. **Prior-season curve.** Each category (fragrance, beauty, electronics, toys,
   apparel, general) has a curve of discount intensity by day around Black Friday.
   Discounts build through November, peak Thanksgiving to Cyber Monday, and fade the
   week after. These are approximations of patterns reported for recent holiday
   seasons (e.g. Adobe's holiday shopping reports). Edit them as you like.
3. **Expected low.** Estimates the usual street price (from MSRP, "was" prices, and
   what sellers charge now), then the expected best price over the next 7 days.
4. **Probability.** Compares today's lowest price with that expected low and gives a
   probability that it goes lower, plus BUY / TOSS-UP / WAIT.
5. **Your history.** Every run is saved to `data/prices.db`. After a few days of
   runs, the real trend for that product nudges the probability, and confidence goes
   to "high".

**Tip:** run it once a day (or schedule it with cron) for items you're watching.

It is a heuristic, not a guarantee: marketplace sellers can change prices at any time.

## Tests

```bash
python3 -m pytest -q
```
