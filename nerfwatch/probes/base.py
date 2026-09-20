from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Callable

# Rasch difficulty (b) per level, one logit per step. Level 3 is "average" (b=0);
# frontier models live around levels 5-9. The suite picks a 5-level window
# around the target's last ability estimate (adaptive testing).
MAX_LEVEL = 9
LEVEL_B = {lvl: float(lvl - 3) for lvl in range(1, MAX_LEVEL + 1)}

SUFFIX = "\n\nDo not use tools. Reply with only the final answer and nothing else."


@dataclass
class Item:
    family: str
    level: int
    prompt: str
    key: Any
    grade: Callable[["Item", str], float]
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def difficulty(self) -> float:
        return LEVEL_B[self.level]

    @property
    def hash(self) -> str:
        return hashlib.sha256(self.prompt.encode()).hexdigest()[:16]


def strip_fences(text: str) -> str:
    t = text.strip()
    m = re.search(r"```[^\n]*\n(.*?)```", t, re.S)
    if m:
        return m.group(1).strip()
    return t


def last_int(text: str) -> int | None:
    t = strip_fences(text).replace(",", "")
    nums = re.findall(r"-?\d+", t)
    return int(nums[-1]) if nums else None


REFUSAL_RE = re.compile(
    r"\b(i can(?:'|no)?t (?:help|assist|provide|do that|comply)|i(?:'m| am) (?:not able|unable) to|i won(?:'|no)?t (?:help|assist|provide)|"
    r"i must decline|i(?:'m| am) sorry,? but i can|as an ai(?: language model)?,? i can|cannot (?:help|assist) with (?:that|this))\b",
    re.I,
)


def looks_refused(text: str) -> bool:
    head = text.strip()[:400]
    return bool(REFUSAL_RE.search(head))


LAZY_RE = re.compile(r"(\.\.\.|…|\betc\.?\b|and so on|continues? (?:in )?(?:this|the same) (?:way|pattern)|\[?remaining|\(rest|omitted|truncated)", re.I)
