
#!/usr/bin/env python3
"""
generate_data.py — deterministic synthetic marketing dataset.

Creates ./data/{ad_spend,sales,ga_events,inventory,sku_margins}.csv
covering 10 days (2025-03-01 to 2025-03-10), 12 campaigns, 4 platforms,
8 SKUs, 12 creatives, with five deliberately injected business events.

Run:  python generate_data.py
"""
from __future__ import annotations
import csv
import os
import random
from datetime import date, timedelta

# ------------------------------------------------------------------ config
SEED = 20250301
random.seed(SEED)

START = date(2025, 3, 1)
N_DAYS = 10
DATES = [START + timedelta(days=i) for i in range(N_DAYS)]

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(OUT_DIR, exist_ok=True)

# ------------------------------------------------------------------ catalog
SKUS = [
    ("SKU-1001", "Apparel",     49.00, 19.60, 400),
    ("SKU-1002", "Apparel",     79.00, 31.60, 350),
    ("SKU-1003", "Footwear",   129.00, 51.60, 250),
    ("SKU-1004", "Footwear",   159.00, 55.65, 180),
    ("SKU-1005", "Accessories", 29.00,  8.70, 600),
    ("SKU-1006", "Accessories", 39.00, 15.60, 500),
    ("SKU-1007", "Home",        89.00, 44.50, 300),
    ("SKU-1008", "Home",       119.00, 47.60, 220),
]
SKU_INFO = {s[0]: {"category": s[1], "price": s[2], "cost": s[3], "opening": s[4]}
            for s in SKUS}

CAMPAIGNS = [
    ("C-001", "Google",    "CR-101", 320, 12.0, 0.045, 0.035,
        [("SKU-1001", 0.60), ("SKU-1002", 0.40)]),
    ("C-002", "Google",    "CR-102", 280, 11.5, 0.041, 0.032,
        [("SKU-1002", 0.55), ("SKU-1003", 0.45)]),
    ("C-003", "Google",    "CR-103", 240, 13.0, 0.038, 0.030,
        [("SKU-1003", 0.55), ("SKU-1007", 0.45)]),
    ("C-004", "Meta",      "CR-104", 360, 10.0, 0.052, 0.028,
        [("SKU-1004", 0.60), ("SKU-1005", 0.40)]),
    ("C-005", "Meta",      "CR-105", 310,  9.5, 0.048, 0.026,
        [("SKU-1005", 0.60), ("SKU-1006", 0.40)]),
    ("C-006", "Meta",      "CR-106", 260, 10.5, 0.044, 0.024,
        [("SKU-1006", 0.55), ("SKU-1007", 0.45)]),
    ("C-007", "TikTok",    "CR-107", 220,  6.5, 0.062, 0.038,
        [("SKU-1001", 0.50), ("SKU-1002", 0.50)]),
    ("C-008", "TikTok",    "CR-108", 200,  6.0, 0.058, 0.034,
        [("SKU-1002", 0.50), ("SKU-1003", 0.50)]),
    ("C-009", "TikTok",    "CR-109", 180,  6.8, 0.055, 0.031,
        [("SKU-1007", 0.55), ("SKU-1008", 0.45)]),
    ("C-010", "Microsoft", "CR-110", 150, 14.0, 0.033, 0.040,
        [("SKU-1001", 0.50), ("SKU-1004", 0.50)]),
    ("C-011", "Microsoft", "CR-111", 140, 13.5, 0.036, 0.042,
        [("SKU-1004", 0.85), ("SKU-1005", 0.15)]),
    ("C-012", "Microsoft", "CR-112", 130, 14.5, 0.031, 0.038,
        [("SKU-1006", 0.55), ("SKU-1008", 0.45)]),
]

# ------------------------------------------------------------------ events
def e1_high_margin(cid: str, d: int):
    if cid == "C-011" and d >= 2:
        return 1.80, 1.35
    return 1.00, 1.00

def e2_creative_fatigue(cid: str, d: int):
    if cid == "C-007" and d >= 3:
        t = (d - 3) / 6.0
        return (1 - 0.65 * t,
                1 - 0.40 * t,
                t)
    return 1.00, 1.00, 0.0

def e3_conversion_crash(d: int) -> float:
    return {4: 0.55, 5: 0.45, 6: 0.80}.get(d, 1.0)

def e4_platform_shift(platform: str, d: int):
    if d < 4:
        return 1.00, 1.00
    if platform == "Meta":
        return 1.55, 0.85
    if platform == "TikTok":
        return 0.85, 1.20
    if platform == "Microsoft" and d >= 5:
        return 1.00, 1.10
    return 1.00, 1.00

# ------------------------------------------------------------------ sim
stock = {s[0]: s[4] for s in SKUS}

ad_spend_rows: list[dict] = []
sales_rows:    list[dict] = []
ga_rows:       list[dict] = []
inventory_rows: list[dict] = []

for d_idx, dt in enumerate(DATES):
    daily_units   = {s[0]: 0 for s in SKUS}
    daily_revenue = {s[0]: 0.0 for s in SKUS}

    for (cid, platform, creative, base_spend, base_cpm,
         base_ctr, base_cvr, sku_mix) in CAMPAIGNS:

        spend_mult_e1, cvr_mult_e1   = e1_high_margin(cid, d_idx)
        ctr_mult_e2, cvr_mult_e2, fatigue_t = e2_creative_fatigue(cid, d_idx)
        cpm_mult_e4, ctr_mult_e4     = e4_platform_shift(platform, d_idx)
        crash = e3_conversion_crash(d_idx)

        spend = base_spend * spend_mult_e1 * (1 + random.uniform(-0.05, 0.05))
        cpm   = base_cpm   * cpm_mult_e4   * (1 + random.uniform(-0.04, 0.04))
        impressions = max(0, int(round(spend / cpm * 1000)))

        ctr = base_ctr * ctr_mult_e2 * ctr_mult_e4 * (1 + random.uniform(-0.06, 0.06))
        clicks = max(0, int(round(impressions * ctr)))

        cvr = (base_cvr * cvr_mult_e1 * cvr_mult_e2 * crash
               * (1 + random.uniform(-0.08, 0.08)))
        raw_conversions = max(0, int(round(clicks * cvr)))

        units_by_sku = {sku: int(round(raw_conversions * w)) for sku, w in sku_mix}
        top_sku = max(sku_mix, key=lambda x: x[1])[0]
        units_by_sku[top_sku] += raw_conversions - sum(units_by_sku.values())

        for sku in units_by_sku:
            avail = stock.get(sku, 0)
            if units_by_sku[sku] > avail:
                units_by_sku[sku] = max(0, avail)

        campaign_units   = sum(units_by_sku.values())
        campaign_revenue = 0.0

        for sku, u in units_by_sku.items():
            price = SKU_INFO[sku]["price"]
            if u > 0:
                rev = u * price
                campaign_revenue += rev
                daily_units[sku]   += u
                daily_revenue[sku] += rev
                sales_rows.append({
                    "date": dt.isoformat(),
                    "campaign_id": cid,
                    "sku": sku,
                    "units_sold": u,
                    "revenue": round(rev, 2),
                })
            stock[sku] = max(0, stock.get(sku, 0) - u)

        for sku, w in sku_mix:
            sku_clicks    = int(round(clicks * w))
            sessions      = sku_clicks
            product_views = int(round(sessions * 0.92))
            add_to_cart   = int(round(sessions * random.uniform(0.12, 0.20)))
            checkout      = int(round(add_to_cart * random.uniform(0.35, 0.50)))
            purchases     = units_by_sku.get(sku, 0)
            ga_rows.append({
                "date": dt.isoformat(),
                "campaign_id": cid,
                "sku": sku,
                "sessions": sessions,
                "product_views": product_views,
                "add_to_cart": add_to_cart,
                "checkout_initiated": checkout,
                "purchases": purchases,
            })

        roas = round(campaign_revenue / spend, 4) if spend else 0.0
        cpa  = round(spend / campaign_units, 2) if campaign_units else None
        engagement     = max(0.0, 0.75 - 0.55 * fatigue_t
                             + random.uniform(-0.03, 0.03))
        fatigue_score  = (min(1.0, fatigue_t + random.uniform(-0.02, 0.02))
                          if fatigue_t > 0
                          else random.uniform(0.02, 0.10))

        ad_spend_rows.append({
            "date": dt.isoformat(),
            "campaign_id": cid,
            "platform": platform,
            "creative_id": creative,
            "spend": round(spend, 2),
            "impressions": impressions,
            "clicks": clicks,
            "conversions": campaign_units,
            "revenue": round(campaign_revenue, 2),
            "roas": roas,
            "cpa": cpa,
            "ctr": round(clicks / impressions, 6) if impressions else 0.0,
            "conversion_rate": round(campaign_units / clicks, 6) if clicks else 0.0,
            "engagement": round(engagement, 4),
            "fatigue_score": round(fatigue_score, 4),
        })

    for sku in stock:
        closing = stock[sku]
        opening = closing + daily_units[sku]
        inventory_rows.append({
            "date": dt.isoformat(),
            "sku": sku,
            "opening_stock": opening,
            "units_sold": daily_units[sku],
            "closing_stock": closing,
            "stockout_flag": 1 if closing == 0 else 0,
        })

# ------------------------------------------------------------------ sku_margins
margin_rows = []
for sku, cat, price, cost, _ in SKUS:
    margin_rows.append({
        "sku": sku,
        "category": cat,
        "price": price,
        "cost": cost,
        "margin_pct": round((price - cost) / price, 4),
    })

# ------------------------------------------------------------------ writers
def write_csv(path: str, rows: list[dict], fieldnames: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

write_csv(os.path.join(OUT_DIR, "ad_spend.csv"), ad_spend_rows, [
    "date", "campaign_id", "platform", "creative_id",
    "spend", "impressions", "clicks", "conversions", "revenue",
    "roas", "cpa", "ctr", "conversion_rate", "engagement", "fatigue_score",
])
write_csv(os.path.join(OUT_DIR, "sales.csv"), sales_rows, [
    "date", "campaign_id", "sku", "units_sold", "revenue",
])
write_csv(os.path.join(OUT_DIR, "ga_events.csv"), ga_rows, [
    "date", "campaign_id", "sku",
    "sessions", "product_views", "add_to_cart", "checkout_initiated", "purchases",
])
write_csv(os.path.join(OUT_DIR, "inventory.csv"), inventory_rows, [
    "date", "sku", "opening_stock", "units_sold", "closing_stock", "stockout_flag",
])
write_csv(os.path.join(OUT_DIR, "sku_margins.csv"), margin_rows, [
    "sku", "category", "price", "cost", "margin_pct",
])

print(f"Wrote {len(ad_spend_rows)} ad_spend rows")
print(f"Wrote {len(sales_rows)} sales rows")
print(f"Wrote {len(ga_rows)} ga_events rows")
print(f"Wrote {len(inventory_rows)} inventory rows")
print(f"Wrote {len(margin_rows)} sku_margins rows")
print(f"--> {OUT_DIR}")