
"""
scoring.py — campaign health scores.
"""
from __future__ import annotations
from collections import defaultdict


def campaign_health(ad_spend) -> list[dict]:
    by_campaign = defaultdict(list)
    for r in ad_spend:
        by_campaign[r["campaign_id"]].append(r)

    scores = []
    for cid, rows in by_campaign.items():
        rows = sorted(rows, key=lambda r: r["date"])
        spend  = sum(r["spend"]        for r in rows)
        rev    = sum(r["revenue"]      for r in rows)
        convs  = sum(r["conversions"]  for r in rows)
        clicks = sum(r["clicks"]       for r in rows) or 1
        roas = rev / spend if spend else 0.0
        cvr  = convs / clicks
        fat  = sum(r["fatigue_score"] for r in rows) / len(rows)

        roas_norm = min(roas / 10.0, 1.0)
        cvr_norm  = min(cvr  / 0.05, 1.0)
        fat_norm  = 1.0 - min(fat / 1.0, 1.0)

        score = 100 * (0.5 * roas_norm + 0.3 * cvr_norm + 0.2 * fat_norm)

        scores.append({
            "campaign_id": cid,
            "platform":    rows[0]["platform"],
            "roas":        round(roas, 2),
            "cvr":         round(cvr, 4),
            "avg_fatigue": round(fat, 3),
            "health_score": round(score, 1),
        })
    return sorted(scores, key=lambda r: -r["health_score"])