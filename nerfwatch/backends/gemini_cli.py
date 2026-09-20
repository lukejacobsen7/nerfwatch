"""Gemini CLI. `gemini -p ... -o json`.

Untested on the author's machine: Google moved individual accounts off the
CLI in 2026 and it now errors at auth. Left in for people whose CLI still works;
open an issue with the JSON shape if it's wrong.
"""

from __future__ import annotations

import json

from .base import Backend, Response, run_cli


class GeminiCliBackend(Backend):
    name = "gemini-cli"

    def complete(self, prompt: str) -> Response:
        argv = ["gemini", "-p", prompt, "-o", "json", "--approval-mode", "plan"]
        if self.model:
            argv += ["-m", self.model]
        out, err, rc, wall = run_cli(argv, self.timeout_s)
        start = out.find("{")
        try:
            d = json.loads(out[start:]) if start >= 0 else {}
        except Exception:  # noqa: BLE001
            return Response(text="", latency_ms=wall, error=f"bad json (rc={rc}): {(err or out)[-200:]}")
        text = d.get("response") or d.get("result") or d.get("text") or ""
        if not text:
            return Response(text="", latency_ms=wall, error=f"empty (rc={rc}): {(err or out)[-200:]}", raw=d)
        stats = d.get("stats") or {}
        return Response(text=text, latency_ms=wall, output_tokens=(stats.get("output_tokens") if isinstance(stats, dict) else None), model_reported=self.model, raw={})
