"""Run the suite against one target and store everything."""

from __future__ import annotations

import datetime as dt
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from . import backends, db
from .probes import Item, build, effort_is_lazy
from .probes import identity as ident
from .probes.base import looks_refused


def _one(be: backends.Backend, item: Item) -> dict[str, Any]:
    try:
        r = be.complete(item.prompt)
    except Exception as e:  # noqa: BLE001
        r = backends.Response(text="", latency_ms=0, error=f"{type(e).__name__}: {str(e)[:160]}")
    score = None if r.error else item.grade(item, r.text)
    return {
        "item_hash": item.hash,
        "family": item.family,
        "level": item.level,
        "difficulty": item.difficulty,
        "score": score,
        "latency_ms": r.latency_ms if not r.error else None,
        "ttft_ms": r.ttft_ms,
        "output_tokens": r.output_tokens,
        "reasoning_tokens": r.reasoning_tokens,
        "output_chars": len(r.text) if not r.error else None,
        "refused": int(bool(r.text) and looks_refused(r.text)),
        "lazy": int(bool(r.text) and effort_is_lazy(item, r.text)),
        "error": r.error,
        "response": r.text[:4000],
        "_model": r.model_reported,
    }


def run_target(cfg: dict[str, Any], target: dict[str, Any], quick: bool = False, parallel: int = 3, verbose: bool = True) -> int:
    be = backends.make(target, timeout_s=int(cfg.get("request_timeout_s", 180)))
    items, suite_hash = build(cfg["salt"], int(cfg.get("items_per_family", 5)), quick=quick, rotation=cfg.get("rotation", "weekly"))
    t0 = time.time()
    if verbose:
        print(f"[{target['name']}] {len(items)} items, suite {suite_hash}, {be.name}" + (f" model={target.get('model')}" if target.get("model") else ""), flush=True)
    with ThreadPoolExecutor(max_workers=max(1, parallel)) as ex:
        results = list(ex.map(lambda it: _one(be, it), items))
    model_reported = next((r["_model"] for r in results if r.get("_model")), None)

    identity_rows: list[dict[str, Any]] = []
    if be.supports_logprobs and not quick:
        probes = ident.select(cfg["salt"], int(cfg.get("identity_probes", 24)))
        with ThreadPoolExecutor(max_workers=max(1, parallel)) as ex:
            lps = list(ex.map(be.logprob_probe, probes))
        for p, lp in zip(probes, lps):
            if lp is None:
                continue
            identity_rows.append({"probe_hash": ident.probe_hash(p), "top_token": lp.top_token, "top_logprob": lp.top_logprob, "top5": lp.top5, "system_fingerprint": lp.system_fingerprint})

    n_err = sum(1 for r in results if r["error"])
    scored = [r["score"] for r in results if r["score"] is not None]
    meta = {
        "wall_s": round(time.time() - t0, 1),
        "hour_local": dt.datetime.now().hour,
        "weekday": dt.datetime.now().weekday(),
        "n_errors": n_err,
        "n_identity": len(identity_rows),
        "accuracy": (sum(scored) / len(scored)) if scored else None,
        "first_error": next((r["error"] for r in results if r["error"]), None),
    }
    with db.connect() as con:
        run_id = db.new_run(con, target, suite_hash, len(items), quick)
        for r in results:
            r.pop("_model", None)
            db.add_result(con, run_id, r)
        if identity_rows:
            db.add_identity(con, run_id, identity_rows)
        db.finish_run(con, run_id, model_reported, meta)
    if verbose:
        acc = f"{meta['accuracy']*100:.0f}%" if meta["accuracy"] is not None else "n/a"
        print(f"[{target['name']}] run #{run_id} done in {meta['wall_s']}s: accuracy {acc} ({len(scored)}/{len(items)} scored, {n_err} errors)"
              + (f", identity probes {len(identity_rows)}" if identity_rows else "")
              + (f", model={model_reported}" if model_reported else ""), flush=True)
        if n_err and meta["first_error"]:
            print(f"[{target['name']}] first error: {meta['first_error']}", file=sys.stderr, flush=True)
    return run_id
