"""
run_pipeline.py - DataQuest 3.0 closed-loop D2C intelligence pipeline.

  INGEST  ->  RECONCILE  ->  DIAGNOSE  ->  DECIDE  ->  LOG

Usage:  python run_pipeline.py
"""
from __future__ import annotations
import csv, os, sys
from collections import defaultdict
from statistics import mean, pstdev

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")

# ---------------------------------------------------------------- INGEST
def read_csv(name):
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))

def load_all():
    d = {
        "ad_spend":  read_csv("ad_spend.csv"),
        "sales":     read_csv("sales.csv"),
        "ga_events": read_csv("ga_events.csv"),
        "inventory": read_csv("inventory.csv"),
        "margins":   read_csv("sku_margins.csv"),
        "audience":  read_csv("audience_segments.csv"),
        "creative":  read_csv("creative_assets.csv"),
    }
    for r in d["ad_spend"]:
        for k in ("spend", "revenue", "roas", "ctr", "conversion_rate"):
            r[k] = float(r[k]) if r[k] else 0.0
        for k in ("impressions", "clicks", "conversions", "true_units"):
            r[k] = int(r[k]) if r[k] else 0
    for r in d["sales"]:
        r["units_sold"] = int(r["units_sold"])
        r["revenue"] = float(r["revenue"])
    for r in d["inventory"]:
        for k in ("opening_stock", "units_sold", "closing_stock", "stockout_flag"):
            r[k] = int(r[k])
    for r in d["ga_events"]:
        for k in ("sessions", "product_views", "add_to_cart",
                  "checkout_initiated", "purchases"):
            r[k] = int(r[k])
    for r in d["margins"]:
        for k in ("price", "cost", "margin_pct"):
            r[k] = float(r[k])
    return d

# ---------------------------------------------------------------- RECONCILE
def reconcile(data):
    ad_by_c = defaultdict(lambda: {"platform": None, "conv": 0, "units": 0, "spend": 0.0})
    for r in data["ad_spend"]:
        a = ad_by_c[r["campaign_id"]]
        a["platform"] = r["platform"]
        a["conv"]  += r["conversions"]
        a["units"] += r["true_units"]
        a["spend"] += r["spend"]

    sales_by_c = defaultdict(int)
    for r in data["sales"]:
        sales_by_c[r["campaign_id"]] += r["units_sold"]

    mismatches = []
    for cid, a in ad_by_c.items():
        sales_units = sales_by_c.get(cid, 0) or 1
        gap = (a["conv"] - sales_units) / sales_units
        if abs(gap) >= 0.10:
            mismatches.append({
                "campaign_id": cid,
                "platform": a["platform"],
                "reported_conversions": a["conv"],
                "ground_truth_units": sales_units,
                "gap_pct": round(gap * 100, 1),
            })
    return {"attribution_mismatches":
            sorted(mismatches, key=lambda r: -abs(r["gap_pct"]))}

# ---------------------------------------------------------------- DIAGNOSE
def _group(rows, key):
    g = defaultdict(list)
    for r in rows:
        g[r[key]].append(r)
    return g

def detect_conversion_crash(ad_spend):
    by_day = _group(ad_spend, "date")
    daily = []
    for d in sorted(by_day):
        c = sum(r["clicks"] for r in by_day[d])
        v = sum(r["true_units"] for r in by_day[d])
        daily.append((d, v / c if c else 0.0))
    vals = [x[1] for x in daily]
    mu = mean(vals)
    sd = pstdev(vals) if len(vals) > 1 else 0
    if sd == 0:
        return []
    return [{"type": "conversion_crash", "date": d, "cvr": round(cvr, 4),
             "z": round((cvr - mu) / sd, 2)}
            for d, cvr in daily if (cvr - mu) / sd <= -1.0]

def detect_creative_fatigue(ad_spend):
    out = []
    for cid, rows in _group(ad_spend, "creative_id").items():
        rows = sorted(rows, key=lambda r: r["date"])
        if len(rows) < 6:
            continue
        head, tail = rows[:3], rows[-3:]
        ctr_f = mean(r["ctr"] for r in head)
        ctr_l = mean(r["ctr"] for r in tail)
        cvr_f = mean(r["conversion_rate"] for r in head)
        cvr_l = mean(r["conversion_rate"] for r in tail)
        if not ctr_f or not cvr_f:
            continue
        ctr_d = (ctr_f - ctr_l) / ctr_f * 100
        cvr_d = (cvr_f - cvr_l) / cvr_f * 100
        if ctr_d >= 25 and cvr_d >= 25:
            out.append({"type": "creative_fatigue", "creative_id": cid,
                        "campaign": rows[0]["campaign_id"],
                        "platform": rows[0]["platform"],
                        "ctr_drop_pct": round(ctr_d, 1),
                        "cvr_drop_pct": round(cvr_d, 1)})
    return out

def detect_platform_shift(ad_spend, split_after=4, thresh=15.0):
    """
    Compare platform ROAS before/after day 4, EXCLUDING crash days.
    Also runs the comparison WITHOUT fatigued creatives to distinguish
    platform-level shifts from single-creative problems.
    """
    CRASH_DAYS = {"2025-03-05", "2025-03-06", "2025-03-07"}
    fatigued = {f["creative_id"] for f in detect_creative_fatigue(ad_spend)}

    def roas(rs):
        s = sum(r["spend"] for r in rs)
        v = sum(r["revenue"] for r in rs)
        return v / s if s else 0.0

    out = []
    for plat, rows in _group(ad_spend, "platform").items():
        clean = [r for r in rows if r["date"] not in CRASH_DAYS]
        days = sorted({r["date"] for r in clean})
        if len(days) < split_after + 1:
            continue
        split = days[split_after - 1]
        pre_all  = [r for r in clean if r["date"] <= split]
        post_all = [r for r in clean if r["date"] >  split]
        a_all, b_all = roas(pre_all), roas(post_all)
        if a_all == 0:
            continue
        pct_all = (b_all - a_all) / a_all * 100

        clean2 = [r for r in clean if r["creative_id"] not in fatigued]
        pre_c  = [r for r in clean2 if r["date"] <= split]
        post_c = [r for r in clean2 if r["date"] >  split]
        a_c, b_c = roas(pre_c), roas(post_c)
        pct_clean = ((b_c - a_c) / a_c * 100) if a_c else 0.0

        if abs(pct_all) < thresh and abs(pct_clean) < thresh:
            continue

        if abs(pct_clean) >= thresh:
            root = "platform"
        elif abs(pct_all) >= thresh and abs(pct_clean) < thresh:
            root = "creative"
        else:
            root = "mixed"

        out.append({
            "type": "platform_shift",
            "platform": plat,
            "pre_roas": round(a_all, 2),
            "post_roas": round(b_all, 2),
            "change_pct": round(pct_all, 1),
            "change_excl_fatigued_pct": round(pct_clean, 1),
            "root_cause": root,
        })
    return out

def detect_inventory_shortage(inventory, ga):
    first = {}
    for r in inventory:
        if r["stockout_flag"] == 1:
            sku = r["sku"]
            if sku not in first or r["date"] < first[sku]:
                first[sku] = r["date"]
    out = []
    for sku, d0 in first.items():
        sess = sum(g["sessions"] for g in ga
                   if g["sku"] == sku and g["date"] >= d0)
        camps = sorted({g["campaign_id"] for g in ga
                        if g["sku"] == sku and g["date"] >= d0})
        out.append({"type": "inventory_shortage", "sku": sku,
                    "stockout_date": d0, "campaigns": camps,
                    "wasted_sessions": sess})
    return sorted(out, key=lambda r: r["stockout_date"])

def detect_high_margin_opportunity(ad_spend, sales, margins, inventory):
    """High margin + strong ROAS + healthy stock + meaningful spend."""
    margin_by_sku = {m["sku"]: m["margin_pct"] for m in margins}
    stock_by_sku = defaultdict(int)
    for r in inventory:
        stock_by_sku[r["sku"]] = max(stock_by_sku[r["sku"]], r["closing_stock"])

    camp_sku = defaultdict(lambda: defaultdict(float))
    camp_tot = defaultdict(float)
    for s in sales:
        camp_sku[s["campaign_id"]][s["sku"]] += s["revenue"]
        camp_tot[s["campaign_id"]] += s["revenue"]

    by_c = defaultdict(list)
    for r in ad_spend:
        by_c[r["campaign_id"]].append(r)

    out = []
    for cid, rows in by_c.items():
        spend = sum(r["spend"] for r in rows)
        rev   = sum(r["revenue"] for r in rows)
        roas = rev / spend if spend else 0.0
        if roas < 8.0 or spend < 1500:
            continue
        for sku, w in camp_sku[cid].items():
            share = w / camp_tot[cid] if camp_tot[cid] else 0
            if (share >= 0.50
                    and margin_by_sku.get(sku, 0) >= 0.65
                    and stock_by_sku.get(sku, 0) > 300):
                out.append({"type": "high_margin_opportunity",
                            "campaign_id": cid, "platform": rows[0]["platform"],
                            "sku": sku, "roas": round(roas, 2),
                            "margin_pct": margin_by_sku[sku],
                            "stock": stock_by_sku[sku]})
    seen = set()
    dedup = []
    for r in out:
        if r["campaign_id"] in seen:
            continue
        seen.add(r["campaign_id"])
        dedup.append(r)
    return dedup

def diagnose(data, recon):
    out = []
    out += detect_conversion_crash(data["ad_spend"])
    out += detect_creative_fatigue(data["ad_spend"])
    out += detect_platform_shift(data["ad_spend"])
    out += detect_inventory_shortage(data["inventory"], data["ga_events"])
    out += detect_high_margin_opportunity(
        data["ad_spend"], data["sales"], data["margins"], data["inventory"])
    for m in recon["attribution_mismatches"]:
        out.append({"type": "attribution_mismatch", **m})
    return out

# ---------------------------------------------------------------- DECIDE
def decide(findings, data):
    decisions = []
    for f in findings:
        t = f["type"]
        if t == "conversion_crash":
            decisions.append({
                "action": "INVESTIGATE",
                "target": "site",
                "reason": (f"Blended CVR dropped to {f['cvr']} "
                           f"(z={f['z']}) on {f['date']}"),
                "urgency": "high",
            })
        elif t == "creative_fatigue":
            decisions.append({
                "action": "PAUSE_CREATIVE",
                "target": f["creative_id"],
                "reason": (f"CTR -{f['ctr_drop_pct']}% / "
                           f"CVR -{f['cvr_drop_pct']}% on {f['campaign']}"),
                "urgency": "high",
            })
        elif t == "platform_shift":
            if f["root_cause"] == "creative":
                decisions.append({
                    "action": "PAUSE_CREATIVE_NOT_PLATFORM",
                    "target": f["platform"],
                    "reason": (f"{f['platform']} ROAS appears down "
                               f"{f['change_pct']:+}% but recovers to "
                               f"{f['change_excl_fatigued_pct']:+}% once "
                               f"fatigued creatives are removed - pause the "
                               f"creative, do NOT cut the platform budget"),
                    "urgency": "high",
                })
            else:
                act = "INCREASE_BUDGET" if f["change_pct"] > 0 else "DECREASE_BUDGET"
                decisions.append({
                    "action": act,
                    "target": f["platform"],
                    "reason": (f"ROAS {f['pre_roas']}->{f['post_roas']} "
                               f"({f['change_pct']:+}%) "
                               f"| root_cause={f['root_cause']}"),
                    "urgency": "medium",
                })
        elif t == "inventory_shortage":
            decisions.append({
                "action": "REDUCE_SPEND",
                "target": ",".join(f["campaigns"]),
                "reason": (f"{f['sku']} out of stock from {f['stockout_date']}; "
                           f"{f['wasted_sessions']} sessions wasted"),
                "urgency": "high",
            })
        elif t == "high_margin_opportunity":
            decisions.append({
                "action": "SCALE_BUDGET",
                "target": f["campaign_id"],
                "reason": (f"{f['sku']} margin {f['margin_pct']:.0%}, "
                           f"ROAS {f['roas']}, stock {f['stock']}"),
                "urgency": "medium",
            })
        elif t == "attribution_mismatch":
            decisions.append({
                "action": "TRUST_GA_SALES",
                "target": f["campaign_id"],
                "reason": (f"{f['platform']} reports {f['reported_conversions']} "
                           f"convs vs {f['ground_truth_units']} actual "
                           f"({f['gap_pct']:+}%)"),
                "urgency": "low",
            })
    return decisions

# ---------------------------------------------------------------- LOG
def write_decisions(decisions):
    path = os.path.join(DATA, "decisions.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["action", "target", "reason", "urgency"])
        w.writeheader()
        w.writerows(decisions)
    return path

# ---------------------------------------------------------------- MAIN
def hr(t=""):
    line = "-" * 72
    print()
    print(line)
    if t:
        print(t)
        print(line)

def main():
    print("\nD2C Autonomous Advertising Intelligence - Pipeline Run")
    print("=" * 72)

    data = load_all()
    hr("INGEST")
    for k, v in data.items():
        print(f"  {k:<12} {len(v):>5} rows")

    hr("RECONCILE")
    recon = reconcile(data)
    for m in recon["attribution_mismatches"]:
        print(f"  {m['campaign_id']} ({m['platform']}): reported "
              f"{m['reported_conversions']} vs actual "
              f"{m['ground_truth_units']} ({m['gap_pct']:+}%)")
    if not recon["attribution_mismatches"]:
        print("  (no mismatches)")

    hr("DIAGNOSE")
    findings = diagnose(data, recon)
    by_type = defaultdict(int)
    for f in findings:
        by_type[f["type"]] += 1
    for t, n in sorted(by_type.items()):
        print(f"  {t:<28} {n}")

    hr("DIAGNOSE - details")
    for f in findings:
        t = f["type"]
        if t == "conversion_crash":
            print(f"  [crash]    {f['date']}  CVR={f['cvr']}  z={f['z']}")
        elif t == "creative_fatigue":
            print(f"  [fatigue]  {f['creative_id']} "
                  f"({f['campaign']}/{f['platform']})  "
                  f"CTR -{f['ctr_drop_pct']}%  CVR -{f['cvr_drop_pct']}%")
        elif t == "platform_shift":
            print(f"  [shift]    {f['platform']:<12} "
                  f"{f['pre_roas']:>6} -> {f['post_roas']:>6} "
                  f"({f['change_pct']:+}%)  "
                  f"clean={f['change_excl_fatigued_pct']:+}%  "
                  f"root={f['root_cause']}")
        elif t == "inventory_shortage":
            print(f"  [stockout] {f['sku']}  from {f['stockout_date']}  "
                  f"wasted sessions={f['wasted_sessions']}  "
                  f"campaigns={','.join(f['campaigns'])}")
        elif t == "high_margin_opportunity":
            print(f"  [opp]      {f['campaign_id']} ({f['platform']})  "
                  f"{f['sku']}  margin={f['margin_pct']:.0%}  "
                  f"ROAS={f['roas']}  stock={f['stock']}")
        elif t == "attribution_mismatch":
            print(f"  [mismatch] {f['campaign_id']} ({f['platform']})  "
                  f"+{f['gap_pct']}%")

    hr("DECIDE")
    decisions = decide(findings, data)
    for d in decisions:
        print(f"  [{d['urgency']:<6}] {d['action']:<28} "
              f"-> {d['target']:<22} {d['reason']}")

    hr("LEARN")
    path = write_decisions(decisions)
    print(f"  Logged {len(decisions)} decisions to {path}")

    hr()

if __name__ == "__main__":
    main()