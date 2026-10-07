
#!/usr/bin/env python3
"""
generate_data.py - D2C multi-platform marketing dataset (DataQuest 3.0).

10 days | 5 platforms | 15 campaigns | 10 SKUs | 15 creatives
Six deliberately injected business events:
  E1  High-margin opportunity        (Amazon / SKU-1004)
  E2  Creative fatigue               (TikTok / CR-107)
  E3  Cross-platform efficiency shift (Meta ROAS collapses)
  E4  Inventory shortage             (SKU-1007 stockout)
  E5  Sitewide conversion crash      (days 5-7)
  E6  Attribution mismatch           (Meta reports more convs than sales)
"""
from __future__ import annotations
import csv, os, random
from datetime import date, timedelta

SEED = 20250301
random.seed(SEED)
START = date(2025, 3, 1)
N_DAYS = 10
DATES = [START + timedelta(days=i) for i in range(N_DAYS)]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(OUT, exist_ok=True)

# sku, category, price, cost, opening_stock
SKUS = [
    ("SKU-1001", "Apparel",     49.00, 19.60, 1500),
    ("SKU-1002", "Apparel",     79.00, 31.60, 1500),
    ("SKU-1003", "Footwear",   129.00, 51.60, 1200),
    ("SKU-1004", "Footwear",   159.00, 55.65, 1400),   # E1 hero (65% margin)
    ("SKU-1005", "Accessories", 29.00,  8.70, 2000),
    ("SKU-1006", "Accessories", 39.00, 15.60, 1500),
    ("SKU-1007", "Home",        89.00, 44.50,  180),   # E4 stockout
    ("SKU-1008", "Home",       119.00, 47.60, 1000),
    ("SKU-1009", "Beauty",      69.00, 17.25, 1200),
    ("SKU-1010", "Beauty",      99.00, 24.75, 1000),
]
SKU_INFO = {s[0]: {"category": s[1], "price": s[2], "cost": s[3], "opening": s[4]}
            for s in SKUS}

# campaign_id, platform, creative_id, base_spend, base_cpm, base_ctr, base_cvr, sku_mix
CAMPAIGNS = [
    ("C-001", "Google",       "CR-101", 320, 12.0, 0.045, 0.035,
        [("SKU-1001", 0.6), ("SKU-1002", 0.4)]),
    ("C-002", "Google",       "CR-102", 280, 11.5, 0.041, 0.032,
        [("SKU-1002", 0.5), ("SKU-1003", 0.5)]),
    ("C-003", "Google",       "CR-103", 240, 13.0, 0.038, 0.030,
        [("SKU-1003", 0.5), ("SKU-1007", 0.5)]),
    ("C-004", "Meta",         "CR-104", 360, 10.0, 0.052, 0.028,
        [("SKU-1004", 0.6), ("SKU-1005", 0.4)]),
    ("C-005", "Meta",         "CR-105", 310,  9.5, 0.048, 0.026,
        [("SKU-1005", 0.6), ("SKU-1006", 0.4)]),
    ("C-006", "Meta",         "CR-106", 260, 10.5, 0.044, 0.024,
        [("SKU-1006", 0.5), ("SKU-1007", 0.5)]),
    ("C-007", "TikTok",       "CR-107", 220,  6.5, 0.062, 0.038,
        [("SKU-1001", 0.5), ("SKU-1002", 0.5)]),       # E2 fatigue
    ("C-008", "TikTok",       "CR-108", 200,  6.0, 0.058, 0.034,
        [("SKU-1002", 0.5), ("SKU-1003", 0.5)]),
    ("C-009", "TikTok",       "CR-109", 180,  6.8, 0.055, 0.031,
        [("SKU-1007", 0.5), ("SKU-1008", 0.5)]),
    ("C-010", "Amazon",       "CR-110", 260, 11.0, 0.041, 0.055,
        [("SKU-1009", 0.5), ("SKU-1010", 0.5)]),
    ("C-011", "Amazon",       "CR-111", 200, 10.5, 0.045, 0.060,
        [("SKU-1004", 0.85), ("SKU-1005", 0.15)]),      # E1 hero
    ("C-012", "Amazon",       "CR-112", 180, 11.5, 0.038, 0.048,
        [("SKU-1003", 0.5), ("SKU-1008", 0.5)]),
    ("C-013", "Programmatic", "CR-113", 140, 14.0, 0.028, 0.022,
        [("SKU-1001", 0.5), ("SKU-1005", 0.5)]),
    ("C-014", "Programmatic", "CR-114", 130, 14.5, 0.026, 0.020,
        [("SKU-1006", 0.5), ("SKU-1009", 0.5)]),
    ("C-015", "Programmatic", "CR-115", 120, 13.5, 0.030, 0.024,
        [("SKU-1008", 0.5), ("SKU-1010", 0.5)]),
]

# ------------------------------------------------------------- events
def e2_fatigue(cid, d):
    if cid == "C-007" and d >= 3:
        t = (d - 3) / 6.0
        return (1 - 0.65 * t, 1 - 0.40 * t, t)
    return 1.0, 1.0, 0.0

def e3_platform_shift(platform, d):
    if d < 4:
        return 1.0, 1.0
    if platform == "Meta":
        return 1.55, 0.85              # CPM up, CTR down
    return 1.0, 1.0

def e5_conversion_crash(d):
    return {4: 0.55, 5: 0.45, 6: 0.80}.get(d, 1.0)

def e6_attribution_multiplier(cid):
    # Meta C-004 overreports conversions to the ad platform
    return 1.30 if cid == "C-004" else 1.0

# ------------------------------------------------------------- simulate
stock = {s[0]: s[4] for s in SKUS}
ad_spend_rows, sales_rows, ga_rows, inv_rows = [], [], [], []
audience_rows, creative_rows = [], []

for d_idx, dt in enumerate(DATES):
    daily_units = {s[0]: 0 for s in SKUS}

    for (cid, platform, creative, base_spend, base_cpm,
         base_ctr, base_cvr, sku_mix) in CAMPAIGNS:

        ctr_m, cvr_m, fat_t = e2_fatigue(cid, d_idx)
        cpm_m, ctr_m_e3     = e3_platform_shift(platform, d_idx)
        crash               = e5_conversion_crash(d_idx)

        spend = base_spend * (1 + random.uniform(-0.05, 0.05))
        cpm   = base_cpm * cpm_m * (1 + random.uniform(-0.04, 0.04))
        impressions = max(0, int(round(spend / cpm * 1000)))

        ctr = base_ctr * ctr_m * ctr_m_e3 * (1 + random.uniform(-0.06, 0.06))
        clicks = max(0, int(round(impressions * ctr)))

        cvr = base_cvr * cvr_m * crash * (1 + random.uniform(-0.08, 0.08))
        true_conversions = max(0, int(round(clicks * cvr)))

        units_by_sku = {sku: int(round(true_conversions * w)) for sku, w in sku_mix}
        top_sku = max(sku_mix, key=lambda x: x[1])[0]
        units_by_sku[top_sku] += true_conversions - sum(units_by_sku.values())

        # inventory cap (E4 fires here)
        for sku in units_by_sku:
            units_by_sku[sku] = max(0, min(units_by_sku[sku], stock.get(sku, 0)))

        units_actual = sum(units_by_sku.values())
        revenue = 0.0
        for sku, u in units_by_sku.items():
            if u > 0:
                p = SKU_INFO[sku]["price"]
                revenue += u * p
                daily_units[sku] += u
                sales_rows.append({
                    "date": dt.isoformat(), "campaign_id": cid,
                    "sku": sku, "units_sold": u, "revenue": round(u * p, 2),
                })
            stock[sku] = max(0, stock.get(sku, 0) - u)

        # GA events (traffic exists even when SKU out of stock)
        for sku, w in sku_mix:
            s = int(round(clicks * w))
            ga_rows.append({
                "date": dt.isoformat(), "campaign_id": cid, "sku": sku,
                "sessions": s, "product_views": int(s * 0.92),
                "add_to_cart": int(s * random.uniform(0.12, 0.20)),
                "checkout_initiated": int(s * random.uniform(0.04, 0.09)),
                "purchases": units_by_sku.get(sku, 0),
            })

        # ad platform reported conversions (E6 inflates some)
        reported_conv = int(round(units_actual * e6_attribution_multiplier(cid)))

        roas = round(revenue / spend, 4) if spend else 0.0
        cpa  = round(spend / units_actual, 2) if units_actual else None

        ad_spend_rows.append({
            "date": dt.isoformat(), "campaign_id": cid, "platform": platform,
            "creative_id": creative, "spend": round(spend, 2),
            "impressions": impressions, "clicks": clicks,
            "conversions": reported_conv, "true_units": units_actual,
            "revenue": round(revenue, 2), "roas": roas, "cpa": cpa,
            "ctr": round(clicks / impressions, 6) if impressions else 0.0,
            "conversion_rate": round(units_actual / clicks, 6) if clicks else 0.0,
        })

        # audience segments
        freq = 1.6 + 0.35 * fat_t * (1 if platform == "TikTok" else 0)
        audience_rows.append({
            "date": dt.isoformat(), "campaign_id": cid, "platform": platform,
            "reach": int(impressions / freq), "frequency": round(freq, 3),
            "impressions": impressions,
        })

        # creative metadata (recomputed per day, latest wins for snapshot)
        creative_rows.append({
            "date": dt.isoformat(), "creative_id": creative,
            "campaign_id": cid, "platform": platform,
            "age_days": d_idx + 1,
            "thumb_stop_rate": round(max(0.05, 0.20 * ctr_m + random.uniform(-0.01, 0.01)), 4),
            "engagement": round(max(0.0, 0.75 - 0.55 * fat_t + random.uniform(-0.03, 0.03)), 4),
            "fatigue_score": round(min(1.0, fat_t + random.uniform(-0.02, 0.02)) if fat_t > 0 else random.uniform(0.02, 0.10), 4),
        })

    for sku in stock:
        closing = stock[sku]
        opening = closing + daily_units[sku]
        inv_rows.append({
            "date": dt.isoformat(), "sku": sku,
            "opening_stock": opening, "units_sold": daily_units[sku],
            "closing_stock": closing,
            "stockout_flag": 1 if closing == 0 else 0,
        })

margin_rows = [{
    "sku": s[0], "category": s[1], "price": s[2], "cost": s[3],
    "margin_pct": round((s[2] - s[3]) / s[2], 4),
} for s in SKUS]

def write(name, rows, fields):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

write("ad_spend.csv", ad_spend_rows, [
    "date","campaign_id","platform","creative_id","spend","impressions",
    "clicks","conversions","true_units","revenue","roas","cpa","ctr","conversion_rate"])
write("sales.csv", sales_rows, ["date","campaign_id","sku","units_sold","revenue"])
write("ga_events.csv", ga_rows, ["date","campaign_id","sku","sessions",
    "product_views","add_to_cart","checkout_initiated","purchases"])
write("inventory.csv", inv_rows, ["date","sku","opening_stock","units_sold",
    "closing_stock","stockout_flag"])
write("sku_margins.csv", margin_rows, ["sku","category","price","cost","margin_pct"])
write("audience_segments.csv", audience_rows, ["date","campaign_id","platform",
    "reach","frequency","impressions"])
write("creative_assets.csv", creative_rows, ["date","creative_id","campaign_id",
    "platform","age_days","thumb_stop_rate","engagement","fatigue_score"])

print(f"Wrote {len(ad_spend_rows)} ad_spend")
print(f"Wrote {len(sales_rows)} sales")
print(f"Wrote {len(ga_rows)} ga_events")
print(f"Wrote {len(inv_rows)} inventory")
print(f"Wrote {len(margin_rows)} sku_margins")
print(f"Wrote {len(audience_rows)} audience_segments")
print(f"Wrote {len(creative_rows)} creative_assets")
print(f"-> {OUT}")