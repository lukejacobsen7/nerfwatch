"""Config lives in ~/.nerfwatch/config.json (override with $NERFWATCH_HOME).

The `salt` is the important bit: every probe item is generated from
sha256(salt + date + family + index), so your suite is never public and
can't be trained on. Don't share it.
"""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any


def home() -> Path:
    p = Path(os.environ.get("NERFWATCH_HOME", Path.home() / ".nerfwatch"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def config_path() -> Path:
    return home() / "config.json"


def db_path() -> Path:
    return home() / "nerfwatch.db"


DEFAULTS: dict[str, Any] = {
    "salt": None,
    # how many items per family per run. 5 = one at each difficulty level.
    "items_per_family": 5,
    # runs per item for the identity (logprob) layer; API backends only
    "identity_probes": 24,
    # CUSUM: baseline = first N runs, then k=0.5σ, h=4σ
    "baseline_runs": 5,
    "cusum_k": 0.5,
    "cusum_h": 4.0,
    "request_timeout_s": 180,
    "targets": [],
}


def load() -> dict[str, Any]:
    p = config_path()
    if not p.exists():
        return dict(DEFAULTS)
    cfg = dict(DEFAULTS)
    cfg.update(json.loads(p.read_text()))
    return cfg


def save(cfg: dict[str, Any]) -> None:
    config_path().write_text(json.dumps(cfg, indent=2) + "\n")


def ensure_salt(cfg: dict[str, Any]) -> dict[str, Any]:
    if not cfg.get("salt"):
        cfg["salt"] = secrets.token_hex(16)
    return cfg


def target_by_name(cfg: dict[str, Any], name: str) -> dict[str, Any] | None:
    for t in cfg.get("targets", []):
        if t["name"] == name:
            return t
    return None
