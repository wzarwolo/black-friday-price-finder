"""Shared data types."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Offer:
    retailer: str               # e.g. "Walmart", "Perfumania"
    title: str
    price: float                # current selling price in USD
    url: str
    seller: Optional[str] = None        # marketplace seller, if different from retailer
    list_price: Optional[float] = None  # "was"/compare-at/MSRP price if the site shows one
    size_oz: Optional[float] = None     # total fluid ounces (pack multiplier applied)
    in_stock: Optional[bool] = None
    flags: list[str] = field(default_factory=list)  # "tester", "set", "mini", ...

    @property
    def price_per_oz(self) -> Optional[float]:
        if self.size_oz and self.size_oz > 0:
            return round(self.price / self.size_oz, 2)
        return None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["price_per_oz"] = self.price_per_oz
        return d
