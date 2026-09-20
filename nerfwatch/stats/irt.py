"""Rasch (1-parameter IRT) ability estimate.

P(correct | θ, b) = 1 / (1 + exp(-(θ - b)))

Item difficulties b come from the generator's level (design-calibrated, one
logit per level). Ability θ is the MAP estimate under a N(0, 1.5²) prior so a
perfect or zero run still yields a finite number. Reported with its standard
error from the observed information.

Why this instead of raw accuracy: items rotate. A 70% on a hard draw and a
70% on an easy draw are not the same model. θ puts every run on one scale.
"""

from __future__ import annotations

import math


def _p(theta: float, b: float) -> float:
    return 1.0 / (1.0 + math.exp(-(theta - b)))


def rasch_theta(items: list[tuple[float, bool]], prior_sd: float = 1.5, iters: int = 50) -> tuple[float, float]:
    """items: [(difficulty_b, correct)]. Returns (theta, se)."""
    if not items:
        return 0.0, float("inf")
    theta = 0.0
    tau = 1.0 / (prior_sd**2)
    for _ in range(iters):
        g = -tau * theta
        H = -tau
        for b, y in items:
            p = _p(theta, b)
            g += (1.0 if y else 0.0) - p
            H -= p * (1 - p)
        step = g / H
        theta -= step
        if abs(step) < 1e-6:
            break
    info = tau + sum(_p(theta, b) * (1 - _p(theta, b)) for b, _ in items)
    return theta, 1.0 / math.sqrt(info)


def expected_accuracy(theta: float, difficulties: list[float]) -> float:
    if not difficulties:
        return 0.0
    return sum(_p(theta, b) for b in difficulties) / len(difficulties)
