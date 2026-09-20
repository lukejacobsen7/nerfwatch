"""Terminal report."""

from __future__ import annotations

import datetime as dt
from typing import Any

from .analyze import METRIC_DEFS, TargetAnalysis, analyze
from .probes.suite import ORDER


def _fmt(v: float | None, fmt: str) -> str:
    return "  -  " if v is None else fmt.format(v)


def _arrow(cur: float | None, base: float | None, better: str) -> str:
    if cur is None or base is None or better == "none":
        return " "
    if abs(cur - base) < 1e-9:
        return "="
    up = cur > base
    good = (up and better == "up") or (not up and better == "down")
    return ("↑" if up else "↓") + ("" if good else "!")


def render(ta: TargetAnalysis) -> str:
    out: list[str] = []
    rs = ta.runs
    out.append(f"== {ta.target} ==  {len(rs)} runs" + (f", last {dt.datetime.fromtimestamp(rs[-1].ts):%Y-%m-%d %H:%M}" if rs else ""))
    if rs and rs[-1].model:
        out.append(f"   model reported: {rs[-1].model}" + (f"   fingerprint: {rs[-1].fingerprint}" if rs[-1].fingerprint else ""))
    if not rs:
        return "\n".join(out)
    base = rs[: ta.baseline_n]
    out.append(f"   {'metric':32} {'baseline':>10} {'last':>10}  trend")
    for key, label, better, fmt in METRIC_DEFS:
        s = ta.series.get(key)
        if not s:
            continue
        bvals = [getattr(m, key) for m in base if getattr(m, key) is not None]
        bmean = sum(bvals) / len(bvals) if bvals else None
        last = getattr(rs[-1], key)
        flag = "  ⚠ " + s.cusum.direction if s.cusum and s.cusum.alarmed else ""
        out.append(f"   {label:32} {_fmt(bmean, fmt):>10} {_fmt(last, fmt):>10}  {_arrow(last, bmean, better)}{flag}")
    out.append("   per-family accuracy (baseline → last):")
    for f in ORDER:
        bv = [m.by_family.get(f) for m in base if m.by_family.get(f) is not None]
        b = sum(bv) / len(bv) if bv else None
        l = rs[-1].by_family.get(f)
        out.append(f"     {f:10} {_fmt(b, '{:.0%}'):>6} → {_fmt(l, '{:.0%}'):>6} {_arrow(l, b, 'up')}")
    if ta.alarms:
        out.append("   ALARMS:")
        out += [f"     ⚠ {a}" for a in ta.alarms]
    out.append(f"   verdict: {ta.verdict}")
    return "\n".join(out)


def report(cfg: dict[str, Any], targets: list[str]) -> str:
    return "\n\n".join(render(analyze(t, cfg)) for t in targets)
