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
from .base import MAX_LEVEL
from .families import FAMILIES, FAMILY_MAX_LEVEL

ORDER = ["arith", "logic", "listops", "knights", "trace", "chars", "code", "instruct", "effort", "refusal"]


def period_key(rotation: str, when: dt.date | None = None) -> str:
    d = when or dt.date.today()
    if rotation == "frozen":
        return "frozen"
    if rotation == "daily":
        return d.isoformat()
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def window(center: int, n: int) -> list[int]:
    """n levels centred on `center`, clamped to [1, MAX_LEVEL]."""
    lo = max(1, min(center - n // 2, MAX_LEVEL - n + 1))
    return [lo + i for i in range(n)]


def center_from_theta(theta: float | None) -> int:
    """Put the window where the model gets ~50-70% right: that's where a test is most informative."""
    if theta is None:
        return 5  # frontier-ish default; a weak model gets re-centred after one run
    return max(3, min(MAX_LEVEL - 2, round(theta + 3)))


def build(salt: str, items_per_family: int = 5, quick: bool = False, rotation: str = "weekly", when: dt.date | None = None, center: int = 5) -> tuple[list[Item], str]:
    period = period_key(rotation, when)
    items: list[Item] = []
    for fam in ORDER:
        gen = FAMILIES[fam]
        fam_max = FAMILY_MAX_LEVEL.get(fam, MAX_LEVEL)
        if quick:
            levels = [min(center, fam_max)]
        else:
            base = window(center, 5)
            levels = [min(base[i % 5], fam_max) for i in range(items_per_family)]
        for idx, level in enumerate(levels):
            seed = int(hashlib.sha256(f"{salt}|{period}|{fam}|{idx}".encode()).hexdigest(), 16) % (2**63)
            rng = random.Random(seed)
            items.append(gen(rng, level))
    suite_hash = hashlib.sha256("|".join(i.hash for i in items).encode()).hexdigest()[:12]
    return items, suite_hash
