
"""
loader.py — reads the five marketing CSVs from ./data.
"""
from __future__ import annotations
import csv
import os
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(ROOT, "data")


def _read(name: str) -> list[dict]:
    path = os.path.join(DATA_DIR, name)
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _f(v):
    return None if v in (None, "") else float(v)


def _i(v):
    return None if v in (None, "") else int(float(v))


def _d(v):
    return datetime.strptime(v, "%Y-%m-%d").date()


def load_ad_spend() -> list[dict]:
    rows = _read("ad_spend.csv")
    for r in rows:
        r["date"] = _d(r["date"])
        for k in ("spend", "revenue", "roas", "cpa", "ctr",
                  "conversion_rate", "engagement", "fatigue_score"):
            r[k] = _f(r[k])
        for k in ("impressions", "clicks", "conversions"):
            r[k] = _i(r[k])
    return rows


def load_sales() -> list[dict]:
    rows = _read("sales.csv")
    for r in rows:
        r["date"] = _d(r["date"])
        r["units_sold"] = _i(r["units_sold"])
        r["revenue"] = _f(r["revenue"])
    return rows


def load_ga_events() -> list[dict]:
    rows = _read("ga_events.csv")
    for r in rows:
        r["date"] = _d(r["date"])
        for k in ("sessions", "product_views", "add_to_cart",
                  "checkout_initiated", "purchases"):
            r[k] = _i(r[k])
    return rows


def load_inventory() -> list[dict]:
    rows = _read("inventory.csv")
    for r in rows:
        r["date"] = _d(r["date"])
        for k in ("opening_stock", "units_sold", "closing_stock", "stockout_flag"):
            r[k] = _i(r[k])
    return rows


def load_sku_margins() -> list[dict]:
    rows = _read("sku_margins.csv")
    for r in rows:
        for k in ("price", "cost", "margin_pct"):
            r[k] = _f(r[k])
    return rows


def load_all() -> dict:
    return {
        "ad_spend":    load_ad_spend(),
        "sales":       load_sales(),
        "ga_events":   load_ga_events(),
        "inventory":   load_inventory(),
        "sku_margins": load_sku_margins(),
    }