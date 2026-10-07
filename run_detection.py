
"""
run_detection.py — detect the five injected events and print a report.

Usage:  python run_detection.py
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.ingestion import loader
from app.intelligence import events, scoring


def hr(title: str = "") -> None:
    line = "-" * 70
    if title:
        print()
        print(line)
        print(title)
        print(line)
    else:
        print(line)


def main() -> None:
    print()
    print("Marketing Intelligence - Event Detection Report")
    print("=" * 70)

    data = loader.load_all()
    print(f"Loaded: {len(data['ad_spend'])} ad_spend | "
          f"{len(data['sales'])} sales | "
          f"{len(data['ga_events'])} ga_events | "
          f"{len(data['inventory'])} inventory | "
          f"{len(data['sku_margins'])} sku_margins")

    hr("E3 - Conversion crash (site-wide CVR drop)")
    for r in events.detect_conversion_crash(data["ad_spend"]):
        print(f"  {r['date']}  CVR={r['blended_cvr']:.4f}  z={r['z']:+.2f}  "
              f"clicks={r['clicks']} convs={r['conversions']}")

    hr("E2 - Creative fatigue (CTR + CVR both fell >25%)")
    for r in events.detect_creative_fatigue(data["ad_spend"]):
        print(f"  {r['creative_id']} ({r['campaign']})  "
              f"CTR {r['ctr_first']:.4f}->{r['ctr_last']:.4f} ({r['ctr_drop_pct']:+.1f}%)  "
              f"CVR {r['cvr_first']:.4f}->{r['cvr_last']:.4f} ({r['cvr_drop_pct']:+.1f}%)")

    hr("E4 - Platform performance shift (ROAS pre vs post day 4)")
    for r in events.detect_platform_shift(data["ad_spend"]):
        arrow = "UP" if r["direction"] == "up" else "DOWN"
        print(f"  {r['platform']:<10} {r['pre_roas']:>6.2f} -> {r['post_roas']:>6.2f}  "
              f"({r['change_pct']:+.1f}%) {arrow}")

    hr("E5 - Inventory shortage (SKU hit zero stock, demand continued)")
    for r in events.detect_inventory_shortage(data["inventory"], data["ga_events"]):
        print(f"  {r['sku']}  stockout from {r['stockout_date']}  "
              f"campaigns={','.join(r['campaigns_affected'])}  "
              f"sessions_after={r['sessions_after_stockout']}")

    hr("E1 - High-margin opportunity (spend scaled up, ROAS held)")
    for r in events.detect_high_margin_opportunity(data["ad_spend"]):
        print(f"  {r['campaign_id']} ({r['platform']})  "
              f"spend step {r['spend_step_pct']:+.1f}%  "
              f"post-window ROAS={r['post_roas']:.2f}")

    hr("Campaign health scores")
    scores = scoring.campaign_health(data["ad_spend"])
    print("  Top 5:")
    for s in scores[:5]:
        print(f"    {s['campaign_id']} ({s['platform']:<9})  "
              f"score={s['health_score']:>5.1f}  "
              f"ROAS={s['roas']:>5.2f}  CVR={s['cvr']:.4f}  "
              f"fatigue={s['avg_fatigue']:.2f}")
    print("  Bottom 3:")
    for s in scores[-3:]:
        print(f"    {s['campaign_id']} ({s['platform']:<9})  "
              f"score={s['health_score']:>5.1f}  "
              f"ROAS={s['roas']:>5.2f}  CVR={s['cvr']:.4f}  "
              f"fatigue={s['avg_fatigue']:.2f}")

    hr()


if __name__ == "__main__":
    main()