
"""
anomaly.py — small statistics helpers (no numpy/pandas).
"""
from __future__ import annotations
from statistics import mean, pstdev


def zscore_series(values: list[float]) -> list[float]:
    if not values:
        return []
    mu = mean(values)
    sd = pstdev(values) if len(values) > 1 else 0.0
    if sd == 0:
        return [0.0] * len(values)
    return [(v - mu) / sd for v in values]


def linreg_slope(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = mean(xs), mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs)
    return num / den if den else 0.0