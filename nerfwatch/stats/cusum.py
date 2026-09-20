"""Two-sided tabular CUSUM (Page 1954). The detector behind every alarm.

Baseline = the first `baseline_n` observations (mean μ0, sd σ0). After that:
    S+_t = max(0, S+_{t-1} + (x_t - μ0) - k σ0)
    S-_t = max(0, S-_{t-1} - (x_t - μ0) - k σ0)
Alarm when either exceeds h σ0 on `confirm` consecutive runs (default 2). k=0.5, h=4 is the textbook setting: tuned to
catch a sustained 1σ shift fast while ignoring one-off noise.

Why not "score dropped 3%"? Because a single run has sampling noise of that
size. CUSUM accumulates evidence across runs and only fires when the shift is
sustained, which is exactly the shape of a silent nerf.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class Cusum:
    mu0: float
    sd0: float
    s_pos: list[float] = field(default_factory=list)
    s_neg: list[float] = field(default_factory=list)
    alarm_idx: int | None = None  # first index (0-based) an alarm fired
    direction: str | None = None  # "up" | "down"
    k: float = 0.5
    h: float = 4.0

    @property
    def alarmed(self) -> bool:
        return self.alarm_idx is not None

    @property
    def threshold(self) -> float:
        return self.h * self.sd0


def cusum(xs: list[float | None], baseline_n: int = 5, k: float = 0.5, h: float = 4.0, min_sd: float | None = None, confirm: int = 2) -> Cusum | None:
    """`confirm`: the statistic must stay above h·σ for this many consecutive
    observations before an alarm is raised. One wild run is not a nerf."""
    vals = [x for x in xs if x is not None]
    if len(vals) < max(2, min(baseline_n, len(vals))) or len(vals) < 2:
        return None
    base = vals[:baseline_n]
    mu0 = sum(base) / len(base)
    var = sum((v - mu0) ** 2 for v in base) / max(1, len(base) - 1)
    sd0 = math.sqrt(var)
    # a flat baseline (e.g. 5 runs all 100%) would make any deviation infinite; floor it
    if min_sd is not None:
        sd0 = max(sd0, min_sd)
    if sd0 == 0:
        sd0 = max(abs(mu0) * 0.05, 1e-9)
    c = Cusum(mu0=mu0, sd0=sd0, k=k, h=h)
    sp = sn = 0.0
    streak = 0
    for i, x in enumerate(vals):
        z = x - mu0
        sp = max(0.0, sp + z - k * sd0)
        sn = max(0.0, sn - z - k * sd0)
        c.s_pos.append(sp)
        c.s_neg.append(sn)
        over = i >= baseline_n and (sp > h * sd0 or sn > h * sd0)
        streak = streak + 1 if over else 0
        if c.alarm_idx is None and streak >= confirm:
            c.alarm_idx = i - confirm + 1
            c.direction = "up" if sp > sn else "down"
    return c
