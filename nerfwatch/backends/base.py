"""A backend turns a prompt into a Response. That's it.

Two kinds:
  - CLI backends (claude-code, codex, gemini-cli): shell out to the agent you
    already pay for. Works on subscriptions. No logprobs, but latency, tokens
    and (for codex / claude) reasoning tokens come back in the JSON.
  - API backends (openai-compatible, anthropic): direct HTTP. Adds the identity
    layer (single-token logprob probes) when the endpoint supports it.
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Response:
    text: str
    latency_ms: float
    ttft_ms: float | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    model_reported: str | None = None
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class LogprobProbe:
    """Result of a 1-token completion with top-k logprobs."""

    top_token: str
    top_logprob: float
    top5: list[tuple[str, float]]
    system_fingerprint: str | None = None


class Backend:
    name = "base"
    supports_logprobs = False

    def __init__(self, target: dict[str, Any], timeout_s: int = 180):
        self.target = target
        self.model = target.get("model")
        self.timeout_s = timeout_s

    def complete(self, prompt: str) -> Response:  # pragma: no cover - interface
        raise NotImplementedError

    def logprob_probe(self, prompt: str) -> LogprobProbe | None:  # pragma: no cover - interface
        return None

    def doctor(self) -> tuple[bool, str]:
        """Cheap liveness check. Returns (ok, message)."""
        try:
            r = self.complete("Reply with exactly the word: pong")
        except Exception as e:  # noqa: BLE001
            return False, f"{type(e).__name__}: {e}"
        if r.error:
            return False, r.error
        ok = "pong" in r.text.lower()
        return ok, f"{r.text.strip()[:40]!r} in {r.latency_ms:.0f}ms (model={r.model_reported})"


def run_cli(argv: list[str], timeout_s: int, env_drop: tuple[str, ...] = ()) -> tuple[str, str, int, float]:
    """Run a CLI, return (stdout, stderr, rc, wall_ms). stdin is closed."""
    env = dict(os.environ)
    for k in env_drop:
        env.pop(k, None)
    t0 = time.perf_counter()
    p = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        stdin=subprocess.DEVNULL,
        env=env,
    )
    ms = (time.perf_counter() - t0) * 1000
    return p.stdout, p.stderr, p.returncode, ms
