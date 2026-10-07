
"""
events.py — detects the five injected business events.
"""
from __future__ import annotations
from collections import defaultdict
from statistics import mean

from .anomaly import zscore_series


def _group_by(rows, key):
    g = defaultdict(list)
    for r in rows:
        g[r[key]].append(r)
    return g


def _sort(rows):
    return sorted(rows, key=lambda r: r["date"])


def detect_conversion_crash(ad_spend, z_thresh: float = 1.0) -> list[dict]:
    by_day = _group_by(ad_spend, "date")
    days = sorted(by_day)
    daily = []
    for d in days:
        clicks = sum(r["clicks"] for r in by_day[d])
        convs  = sum(r["conversions"] for r in by_day[d])
        cvr = convs / clicks if clicks else 0.0
        daily.append((d, cvr, clicks, convs))
    zs = zscore_series([x[1] for x in daily])
    out = []
    for (d, cvr, clicks, convs), z in zip(daily, zs):
        if z <= -z_thresh:
            out.append({
                "date": d.isoformat(),
                "blended_cvr": round(cvr, 4),
                "z": round(z, 2),
                "clicks": clicks,
                "conversions": convs,
            })
    return out


def detect_creative_fatigue(ad_spend,
                            ctr_drop_pct: float = 25.0,
                            cvr_drop_pct: float = 25.0,
                            head_days: int = 3,
                            tail_days: int = 3) -> list[dict]:
    out = []
    for cid, rows in _group_by(ad_spend, "creative_id").items():
        rows = _sort(rows)
        if len(rows) < head_days + tail_days:
            continue
        head, tail = rows[:head_days], rows[-tail_days:]
        ctr_first = mean(r["ctr"] for r in head)
        ctr_last  = mean(r["ctr"] for r in tail)
        cvr_first = mean(r["conversion_rate"] for r in head)
        cvr_last  = mean(r["conversion_rate"] for r in tail)
        if not ctr_first or not cvr_first:
            continue
        ctr_drop = (ctr_first - ctr_last) / ctr_first * 100
        cvr_drop = (cvr_first - cvr_last) / cvr_first * 100
        if ctr_drop >= ctr_drop_pct and cvr_drop >= cvr_drop_pct:
            out.append({
                "creative_id": cid,
                "campaign": rows[0]["campaign_id"],
                "ctr_first": round(ctr_first, 5),
                "ctr_last":  round(ctr_last, 5),
                "ctr_drop_pct": round(ctr_drop, 1),
                "cvr_first": round(cvr_first, 5),
                "cvr_last":  round(cvr_last, 5),
                "cvr_drop_pct": round(cvr_drop, 1),
            })
    return sorted(out, key=lambda r: -r["ctr_drop_pct"])


def detect_platform_shift(ad_spend,
                          split_after_day: int = 4,
                          change_thresh_pct: float = 10.0) -> list[dict]:
    by_platform = _group_by(ad_spend, "platform")
    out = []
    for platform, rows in by_platform.items():
        days = sorted({r["date"] for r in rows})
        if len(days) <= split_after_day:
            continue
        split = days[split_after_day - 1]
        pre  = [r for r in rows if r["date"] <= split]
        post = [r for r in rows if r["date"] >  split]
        if not pre or not post:
            continue

        def blended_roas(rs):
            s = sum(r["spend"]   for r in rs)
            v = sum(r["revenue"] for r in rs)
            return v / s if s else 0.0

        pre_roas, post_roas = blended_roas(pre), blended_roas(post)
        if pre_roas == 0:
            continue
        pct = (post_roas - pre_roas) / pre_roas * 100
        if abs(pct) >= change_thresh_pct:
            out.append({
                "platform":  platform,
                "pre_roas":  round(pre_roas, 2),
                "post_roas": round(post_roas, 2),
                "change_pct": round(pct, 1),
                "direction": "up" if pct > 0 else "down",
            })
    return sorted(out, key=lambda r: r["change_pct"])


def detect_inventory_shortage(inventory, ga_events) -> list[dict]:
    first_stockout: dict[str, object] = {}
    for r in inventory:
        if r.get("stockout_flag") == 1:
            sku = r["sku"]
            if sku not in first_stockout or r["date"] < first_stockout[sku]:
                first_stockout[sku] = r["date"]

    out = []
    for sku, d0 in first_stockout.items():
        sessions_after = 0
        campaigns = set()
        for g in ga_events:
            if g["sku"] == sku and g["date"] >= d0:
                sessions_after += g["sessions"] or 0
                campaigns.add(g["campaign_id"])
        out.append({
            "sku": sku,
            "stockout_date": d0.isoformat(),
            "campaigns_affected": sorted(campaigns),
            "sessions_after_stockout": sessions_after,
        })
    return sorted(out, key=lambda r: r["stockout_date"])


def detect_high_margin_opportunity(ad_spend,
                                   head_days: int = 3,
                                   tail_days: int = 3,
                                   spend_step_pct: float = 30.0,
                                   min_post_roas: float = 4.0) -> list[dict]:
    out = []
    for cid, rows in _group_by(ad_spend, "campaign_id").items():
        rows = _sort(rows)
        if len(rows) < head_days + tail_days:
            continue
        head, tail = rows[:head_days], rows[-tail_days:]
        pre  = mean(r["spend"] for r in head)
        post = mean(r["spend"] for r in tail)
        if pre == 0:
            continue
        step = (post - pre) / pre * 100
        if step < spend_step_pct:
            continue
        spend_post = sum(r["spend"] for r in tail) or 1e-9
        rev_post   = sum(r["revenue"] for r in tail)
        post_roas  = rev_post / spend_post
        if post_roas < min_post_roas:
            continue
        out.append({
            "campaign_id": cid,
            "platform": rows[0]["platform"],
            "spend_step_pct": round(step, 1),
            "post_roas": round(post_roas, 2),
        })
    return sorted(out, key=lambda r: -r["spend_step_pct"])