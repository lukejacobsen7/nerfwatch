from __future__ import annotations

import random


def mean_ci(xs: list[float], n_boot: int = 1000, alpha: float = 0.05, seed: int = 0) -> tuple[float, float, float]:
    """Percentile bootstrap CI for the mean. Returns (mean, lo, hi)."""
    if not xs:
        return 0.0, 0.0, 0.0
    m = sum(xs) / len(xs)
    if len(xs) < 2:
        return m, m, m
    rng = random.Random(seed)
    n = len(xs)
    means = sorted(sum(rng.choice(xs) for _ in range(n)) / n for _ in range(n_boot))
    lo = means[int(alpha / 2 * n_boot)]
    hi = means[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]
    return m, lo, hi


def median(xs: list[float]) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
