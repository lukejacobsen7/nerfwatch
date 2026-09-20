"""Build a run's item set. Seeded by (salt, period, family, index).

`rotation` controls how often items change:
  frozen  same items forever (max comparability; keep your salt secret)
  weekly  new items each ISO week (default; intra-week comparisons are exact,
          cross-week via Rasch ability which is difficulty-aware)
  daily   new items every day
"""

from __future__ import annotations

import datetime as dt
import hashlib
import random

from . import families  # noqa: F401 - registers FAMILIES
from .base import Item
from .families import FAMILIES

ORDER = ["arith", "logic", "listops", "code", "instruct", "effort", "refusal"]


def period_key(rotation: str, when: dt.date | None = None) -> str:
    d = when or dt.date.today()
    if rotation == "frozen":
        return "frozen"
    if rotation == "daily":
        return d.isoformat()
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def build(salt: str, items_per_family: int = 5, quick: bool = False, rotation: str = "weekly", when: dt.date | None = None) -> tuple[list[Item], str]:
    period = period_key(rotation, when)
    items: list[Item] = []
    for fam in ORDER:
        gen = FAMILIES[fam]
        levels = [3] if quick else [((i % 5) + 1) for i in range(items_per_family)]
        for idx, level in enumerate(levels):
            seed = int(hashlib.sha256(f"{salt}|{period}|{fam}|{idx}".encode()).hexdigest(), 16) % (2**63)
            rng = random.Random(seed)
            items.append(gen(rng, level))
    suite_hash = hashlib.sha256("|".join(i.hash for i in items).encode()).hexdigest()[:12]
    return items, suite_hash
