from datetime import date

from pricefinder import matching
from pricefinder.predict import black_friday, cyber_monday, predict, season_offset, thanksgiving

Q, BRAND = "Daisy Ever So Fresh Eau de Parfum", "Marc Jacobs"


def test_holiday_dates():
    assert thanksgiving(2026) == date(2026, 11, 26)
    assert black_friday(2025) == date(2025, 11, 28)
    assert cyber_monday(2026) == date(2026, 11, 30)
    assert season_offset(date(2026, 11, 26)) == -1


def test_matching_rejects_similar_products():
    assert matching.is_match("Marc Jacobs Daisy Ever So Fresh, 4.2 oz EDP Spray", Q, BRAND)
    assert matching.is_match("Daisy Ever So Fresh by Marc Jacobs 1 oz", Q, BRAND)
    assert not matching.is_match("Daisy Eau So Fresh by Marc Jacobs 4.2 oz EDT", Q, BRAND)
    assert not matching.is_match("Daisy Ever So Fresh Eau de Toilette", Q, BRAND)


def test_url_slug_contradiction():
    bad = "https://www.walmart.com/ip/Daisy-Eau-So-Fresh-by-Marc-Jacobs-4-2-oz-Eau-De-Toilette-Spray-for-Women/5327700954"
    good = "https://www.walmart.com/ip/Marc-Jacobs-Daisy-Ever-So-Fresh-4-2-oz-EDP-Spray/1115447342"
    assert matching.url_contradicts(bad, Q, BRAND)
    assert not matching.url_contradicts(good, Q, BRAND)


def test_size_parsing():
    assert matching.parse_size_oz("Daisy 4.2 oz EDP") == 4.2
    assert matching.parse_size_oz("Daisy 0.34 oz Each, 2-Pack") == 0.68
    assert matching.parse_size_oz("Daisy 100ml") == 3.38
    assert matching.parse_size_oz("Daisy Ever So Fresh") is None


def test_flags():
    assert "tester" in matching.detect_flags("Daisy Ever So Fresh 4.2 oz Tester")
    assert "set" in matching.detect_flags("Daisy Ever So Fresh 3 Piece Gift Set")


def test_deep_discount_on_thanksgiving_says_buy():
    p = predict(Q, current_price=68.99, list_prices=[163.0], market_prices=[68.99, 151.95],
                today=date(2026, 11, 26))
    assert p.category == "fragrance"
    assert p.probability_lower < 0.4
    assert p.recommendation.startswith("BUY")


def test_full_price_before_season_says_wait():
    p = predict(Q, current_price=150.0, list_prices=[163.0], market_prices=[150.0, 155.0, 160.0],
                today=date(2026, 11, 20))
    assert p.probability_lower > 0.6
    assert p.recommendation.startswith("WAIT")


def test_falling_history_raises_probability():
    args = dict(query=Q, current_price=60.0, list_prices=[], market_prices=[60.0], today=date(2026, 11, 26))
    flat = predict(**args)
    falling = predict(**args, daily_lows=[("2026-11-23", 75.0), ("2026-11-24", 70.0), ("2026-11-25", 64.0)])
    assert falling.probability_lower > flat.probability_lower
