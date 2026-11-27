"""Decide whether a listing is really the product you searched for, and parse its size.

Search results are noisy: a search for "Daisy Ever So Fresh" also returns
"Daisy Eau So Fresh" (a different perfume), gift sets, testers and minis.
"""
from __future__ import annotations

import re
from typing import Optional

# Words that describe the format, not the product. They don't have to appear in a title.
GENERIC = {
    "eau", "de", "du", "parfum", "toilette", "cologne", "edp", "edt", "spray", "perfume",
    "fragrance", "for", "women", "woman", "men", "man", "unisex", "by", "the", "and", "&",
    "oz", "fl", "ml", "new", "a", "an", "of", "-", "womens", "mens",
}

CONCENTRATIONS = {
    "edp": ("eau de parfum", "edp", "parfum"),
    "edt": ("eau de toilette", "edt", "toilette"),
}

ML_PER_OZ = 29.5735


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower().replace("'", ""))


def core_tokens(query: str, brand: Optional[str] = None) -> set[str]:
    brand_toks = set(tokens(brand)) if brand else set()
    return {t for t in tokens(query) if t not in GENERIC and t not in brand_toks}


def wanted_concentration(query: str) -> Optional[str]:
    q = query.lower()
    if "toilette" in q or re.search(r"\bedt\b", q):
        return "edt"
    if "parfum" in q or re.search(r"\bedp\b", q):
        return "edp"
    return None


def title_concentration(title: str) -> Optional[str]:
    t = title.lower()
    if "toilette" in t or re.search(r"\bedt\b", t):
        return "edt"
    if "parfum" in t or re.search(r"\bedp\b", t):
        return "edp"
    return None


def is_match(title: str, query: str, brand: Optional[str] = None) -> bool:
    """Every distinctive query word must appear in the title, and the concentration
    (EDP vs EDT) must not contradict the query."""
    title_toks = set(tokens(title))
    if not core_tokens(query, brand) <= title_toks:
        return False
    want = wanted_concentration(query)
    have = title_concentration(title)
    if want and have and want != have:
        return False
    return True


def url_contradicts(url: str, query: str, brand: Optional[str] = None) -> bool:
    """Marketplace sellers sometimes reuse a listing for a different product: the title
    says one thing, the URL slug another. If the slug clearly describes a product
    (shares most of the query's words) but not *this* product, reject it."""
    slug = url.split("?")[0].rstrip("/").rsplit("/", 2)
    slug_text = " ".join(slug[-2:]).replace("-", " ").replace("_", " ")
    slug_toks = set(tokens(slug_text))
    core = core_tokens(query, brand)
    if not core:
        return False
    overlap = len(core & slug_toks) / len(core)
    if 0.5 <= overlap < 1:
        return True
    want, have = wanted_concentration(query), title_concentration(slug_text)
    return overlap == 1 and bool(want and have and want != have)


def detect_flags(title: str) -> list[str]:
    t = title.lower()
    flags = []
    if re.search(r"\btester\b|\bunboxed\b|\bwhite box\b", t):
        flags.append("tester")
    if re.search(r"\bgift set\b|\b\d+\s*-?\s*(pc|piece)s?\b|\bset\b|\bbundle\b|\bcoffret\b|\+", t):
        flags.append("set")
    if re.search(r"\bmini\b|\btravel\b|\brollerball\b|\bsample\b|\bvial\b|\bdecant\b", t):
        flags.append("mini")
    if re.search(r"\bbody (lotion|mist|wash)\b|\bshower gel\b|\bdeodorant\b|\bhair mist\b", t):
        flags.append("not-perfume")
    return flags


def parse_size_oz(title: str) -> Optional[float]:
    """Return total fluid ounces, e.g. '0.34 oz Each, 2-Pack' -> 0.68, '100ml' -> 3.38."""
    t = title.lower()
    size = None
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:fl\.?\s*)?oz\b", t) or re.search(r"(\d+(?:\.\d+)?)\s*-?\s*ounce", t)
    if m:
        size = float(m.group(1))
    else:
        m = re.search(r"(\d+(?:\.\d+)?)\s*ml\b", t)
        if m:
            size = round(float(m.group(1)) / ML_PER_OZ, 2)
    if size is None:
        return None
    pack = re.search(r"(\d+)\s*-?\s*(?:pack|pk|count|ct)\b", t) or re.search(r"\bpack of (\d+)", t)
    if pack:
        size *= int(pack.group(1))
    return round(size, 2)
