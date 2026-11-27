"""Local price history (SQLite). Every search is saved, so running the tool daily
builds a real price trend for each product, which the predictor then uses."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import Offer

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "prices.db"


def _connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS observations (
            id INTEGER PRIMARY KEY,
            observed_at TEXT NOT NULL,
            query TEXT NOT NULL,
            retailer TEXT, seller TEXT, title TEXT, url TEXT,
            price REAL NOT NULL, list_price REAL, size_oz REAL
        )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_query ON observations(query, size_oz)")
    return conn


def normalize_query(query: str) -> str:
    return " ".join(query.lower().split())


def save(query: str, offers: list[Offer], path: Path = DB_PATH) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _connect(path) as conn:
        conn.executemany(
            "INSERT INTO observations (observed_at, query, retailer, seller, title, url, price, list_price, size_oz)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            [(now, normalize_query(query), o.retailer, o.seller, o.title, o.url, o.price, o.list_price, o.size_oz)
             for o in offers],
        )


def daily_lows(query: str, size_oz: float | None, path: Path = DB_PATH) -> list[tuple[str, float]]:
    """Lowest observed price per day for this product/size: [(YYYY-MM-DD, price), ...]."""
    with _connect(path) as conn:
        if size_oz is None:
            rows = conn.execute(
                "SELECT substr(observed_at,1,10) d, MIN(price) FROM observations"
                " WHERE query=? AND size_oz IS NULL GROUP BY d ORDER BY d",
                (normalize_query(query),)).fetchall()
        else:
            rows = conn.execute(
                "SELECT substr(observed_at,1,10) d, MIN(price) FROM observations"
                " WHERE query=? AND abs(size_oz-?)<0.05 GROUP BY d ORDER BY d",
                (normalize_query(query), size_oz)).fetchall()
    return [(d, p) for d, p in rows]
