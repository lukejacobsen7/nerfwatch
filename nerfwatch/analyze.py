"""Turn stored runs into per-run metrics, CUSUM alarms, and a plain-English verdict."""

from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from . import db
from .probes.suite import ORDER
from .stats import Cusum, cusum, median, rasch_theta


@dataclass
class RunMetrics:
    run_id: int
    ts: float
    model: str | None
    suite_hash: str
    quick: bool
    n: int
    accuracy: float | None
    theta: float | None
    theta_se: float | None
    by_family: dict[str, float | None]
    latency_ms: float | None
    ttft_ms: float | None
    output_tokens: float | None
    reasoning_tokens: float | None
    refusal_rate: float | None
    lazy_rate: float | None
    error_rate: float
    ident_logprob: float | None  # mean top-token logprob over identity probes
    ident_agree: float | None  # share of probes whose top token matches the baseline mode
    fingerprint: str | None
    hour: int | None


@dataclass
class Series:
    name: str
    label: str
    values: list[float | None]
    cusum: Cusum | None
    better: str  # "up" | "down" | "none"
    fmt: str = "{:.2f}"


@dataclass
class TargetAnalysis:
    target: str
    runs: list[RunMetrics]
    series: dict[str, Series] = field(default_factory=dict)
    alarms: list[str] = field(default_factory=list)
    verdict: str = ""
    baseline_n: int = 5


METRIC_DEFS = [
    # key, label, better-direction, format
    ("theta", "ability θ (Rasch)", "up", "{:+.2f}"),
    ("accuracy", "accuracy", "up", "{:.0%}"),
    ("latency_ms", "latency ms (median)", "down", "{:.0f}"),
    ("reasoning_tokens", "reasoning tokens (median)", "none", "{:.0f}"),
    ("output_tokens", "output tokens (median)", "none", "{:.0f}"),
    ("refusal_rate", "refusal rate", "down", "{:.0%}"),
    ("lazy_rate", "lazy rate (effort probes)", "down", "{:.0%}"),
    ("ident_logprob", "identity: mean top-5 logprob", "none", "{:.3f}"),
    ("ident_agree", "identity: top-token agreement", "up", "{:.0%}"),
]


def _run_metrics(con: sqlite3.Connection, run: sqlite3.Row, ident_mode: dict[str, str]) -> RunMetrics:
    rows = db.results_for_run(con, run["id"])
    scored = [r for r in rows if r["score"] is not None]
    acc = (sum(r["score"] for r in scored) / len(scored)) if scored else None
    irt_items = [(float(r["difficulty"]), r["score"] >= 0.999) for r in scored if r["family"] != "refusal"]
    theta, se = rasch_theta(irt_items) if irt_items else (None, None)
    fam: dict[str, float | None] = {}
    for f in ORDER:
        fs = [r["score"] for r in scored if r["family"] == f]
        fam[f] = (sum(fs) / len(fs)) if fs else None
    eff = [r for r in rows if r["family"] == "effort" and r["error"] is None]
    ident = db.identity_for_run(con, run["id"])
    # top-1 is usually saturated at ~0 for these prompts; the top-5 mass shape is the sensitive part
    lp = []
    for r in ident:
        try:
            t5 = [float(v[1]) for v in json.loads(r["top5"] or "[]")]
        except (ValueError, TypeError, IndexError):
            t5 = []
        if t5:
            lp.append(sum(t5) / len(t5))
        elif r["top_logprob"] is not None:
            lp.append(float(r["top_logprob"]))
    agree = None
    if ident and ident_mode:
        agree = sum(1 for r in ident if ident_mode.get(r["probe_hash"]) == r["top_token"]) / len(ident)
    meta = json.loads(run["meta"] or "{}")
    return RunMetrics(
        run_id=run["id"], ts=run["ts"], model=run["model_reported"] or run["model_requested"], suite_hash=run["suite_hash"], quick=bool(run["quick"]), n=len(rows),
        accuracy=acc, theta=theta, theta_se=se, by_family=fam,
        latency_ms=median([r["latency_ms"] for r in rows if r["latency_ms"]]),
        ttft_ms=median([r["ttft_ms"] for r in rows if r["ttft_ms"]]),
        output_tokens=median([r["output_tokens"] for r in rows if r["output_tokens"] is not None]),
        reasoning_tokens=median([r["reasoning_tokens"] for r in rows if r["reasoning_tokens"] is not None]),
        refusal_rate=(sum(r["refused"] for r in rows) / len(rows)) if rows else None,
        lazy_rate=(sum(r["lazy"] for r in eff) / len(eff)) if eff else None,
        error_rate=(sum(1 for r in rows if r["error"]) / len(rows)) if rows else 0.0,
        ident_logprob=(sum(lp) / len(lp)) if lp else None,
        ident_agree=agree,
        fingerprint=next((r["system_fingerprint"] for r in ident if r["system_fingerprint"]), None),
        hour=meta.get("hour_local"),
    )


def _ident_mode(con: sqlite3.Connection, runs: list[sqlite3.Row], baseline_n: int) -> dict[str, str]:
    """Most common top token per probe across the baseline runs."""
    votes: dict[str, Counter] = {}
    for run in runs[:baseline_n]:
        for r in db.identity_for_run(con, run["id"]):
            votes.setdefault(r["probe_hash"], Counter())[r["top_token"]] += 1
    return {k: c.most_common(1)[0][0] for k, c in votes.items()}


def analyze(target: str, cfg: dict[str, Any]) -> TargetAnalysis:
    baseline_n = int(cfg.get("baseline_runs", 5))
    k, h = float(cfg.get("cusum_k", 0.5)), float(cfg.get("cusum_h", 4.0))
    with db.connect() as con:
        runs = [r for r in db.runs_for(con, target) if not r["quick"]] or db.runs_for(con, target)
        mode = _ident_mode(con, runs, baseline_n)
        rms = [_run_metrics(con, r, mode) for r in runs]
    ta = TargetAnalysis(target=target, runs=rms, baseline_n=baseline_n)
    n_items = rms[-1].n if rms else 35
    for key, label, better, fmt in METRIC_DEFS:
        vals = [getattr(m, key) for m in rms]
        if all(v is None for v in vals):
            continue
        min_sd = None
        if key == "accuracy":
            p = next((v for v in vals if v is not None), 0.5)
            min_sd = math.sqrt(max(p * (1 - p), 0.05) / max(n_items, 1))  # binomial sampling floor
        elif key == "theta":
            ses = [m.theta_se for m in rms if m.theta_se]
            min_sd = median(ses) or 0.3
        elif key in ("refusal_rate", "lazy_rate", "ident_agree"):
            min_sd = 0.05
        elif key in ("latency_ms", "reasoning_tokens", "output_tokens"):
            # heavy-tailed: run CUSUM on log scale so a 2x shift is the same size at any level
            vals = [math.log(v + 1) if v is not None else None for v in vals]
            min_sd = 0.10
        elif key == "ident_logprob":
            min_sd = 0.15
        c = cusum(vals, baseline_n=baseline_n, k=k, h=h, min_sd=min_sd)
        ta.series[key] = Series(key, label, [getattr(m, key) for m in rms], c, better, fmt)
        if c and c.alarmed:
            when = rms[c.alarm_idx]
            ta.alarms.append(f"{label} shifted {c.direction} (CUSUM alarm at run #{when.run_id})")
    ta.verdict = verdict(ta)
    return ta


def _alarm(ta: TargetAnalysis, key: str, direction: str | None = None) -> bool:
    s = ta.series.get(key)
    if not s or not s.cusum or not s.cusum.alarmed:
        return False
    return direction is None or s.cusum.direction == direction


def verdict(ta: TargetAnalysis) -> str:
    n = len(ta.runs)
    if n == 0:
        return "no runs yet"
    if n <= ta.baseline_n:
        return f"building baseline ({n}/{ta.baseline_n} runs); no verdict until the baseline is full"
    worse = _alarm(ta, "theta", "down")  # accuracy shifts with the adaptive window; θ is the comparable scale
    identity = _alarm(ta, "ident_logprob") or _alarm(ta, "ident_agree", "down")
    juice_cut = _alarm(ta, "reasoning_tokens", "down")
    lazy = _alarm(ta, "lazy_rate", "up")
    slow = _alarm(ta, "latency_ms", "up")
    refuse = _alarm(ta, "refusal_rate", "up")
    parts: list[str] = []
    if identity and worse:
        parts.append("THE MODEL CHANGED AND GOT WORSE: identity probes shifted (new weights / quantization / inference stack) and ability dropped")
    elif identity:
        parts.append("the served model changed (identity probes shifted) but ability is holding")
    elif juice_cut and worse:
        parts.append("REASONING BUDGET CUT: fewer reasoning tokens and lower ability, identity stable. Same weights, less compute")
    elif juice_cut:
        parts.append("reasoning tokens dropped; ability not (yet) affected")
    elif worse:
        parts.append("ABILITY DROPPED with no identity or reasoning-token signal. Cause unclear; check per-family")
    if lazy:
        parts.append("laziness up: effort probes are being skipped/summarized")
    if refuse:
        parts.append("refusals up on benign prompts")
    if slow and not parts:
        parts.append("slower, not dumber: latency shifted, ability stable")
    elif slow:
        parts.append("also slower")
    if not parts:
        return "stable: no sustained shift on any tracked metric"
    return "; ".join(parts)
