
# Marketing Intelligence Dataset

A 10-day synthetic marketing dataset with 5 deliberately injected business events.

## Files
- `data/ad_spend.csv` — daily campaign spend, impressions, clicks, conversions, ROAS, CPA
- `data/sales.csv` — daily units sold and revenue per campaign × SKU
- `data/ga_events.csv` — daily GA funnel events (sessions → purchases)
- `data/inventory.csv` — daily opening/closing stock per SKU
- `data/sku_margins.csv` — SKU price, cost, category, margin

## Regenerate
    python generate_data.py

## Injected events
1. High-margin opportunity (C-011 from day 3)
2. Creative fatigue (C-007 / CR-107 from day 4)
3. Conversion crash (all campaigns, days 5–7)
4. Platform shift (Meta down, TikTok up from day 5)
5. Inventory shortage (SKU-1007 from day 8)