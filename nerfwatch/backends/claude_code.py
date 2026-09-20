"""Claude Code (subscription). Shells out to `claude -p ... --output-format json`.

Notes learned the hard way:
  - When nerfwatch itself is launched from inside a Claude Code session, the
    CLAUDECODE env var makes the child refuse to run. We drop it.
  - --tools "" keeps it from touching the filesystem. We want the raw model.
  - Every call re-sends the system prompt (~80k cached tokens). On a
    subscription that's free money-wise but it does count toward rate limits,
    which is why the default suite is small.
"""

from __future__ import annotations

import json

from .base import Backend, Response, run_cli


class ClaudeCodeBackend(Backend):
    name = "claude-code"

    def complete(self, prompt: str) -> Response:
        argv = ["claude", "-p", prompt, "--output-format", "json", "--no-session-persistence", "--tools", ""]
        if self.model:
            argv += ["--model", self.model]
        if self.target.get("effort"):
            argv += ["--effort", self.target["effort"]]
        out, err, rc, wall = run_cli(argv, self.timeout_s, env_drop=("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT"))
        try:
            d = json.loads(out.strip().splitlines()[-1])
        except Exception:  # noqa: BLE001
            return Response(text="", latency_ms=wall, error=f"bad json (rc={rc}): {(err or out)[:200]}")
        if d.get("is_error"):
            return Response(text="", latency_ms=wall, error=str(d.get("result"))[:200], raw=d)
        usage = d.get("usage") or {}
        mu = d.get("modelUsage") or {}
        reported = None
        for k, v in mu.items():
            reported = v.get("canonicalModel") or k
        return Response(
            text=d.get("result") or "",
            latency_ms=float(d.get("duration_api_ms") or d.get("duration_ms") or wall),
            ttft_ms=d.get("ttft_ms"),
            output_tokens=usage.get("output_tokens"),
            reasoning_tokens=(usage.get("output_tokens_details") or {}).get("thinking_tokens"),
            model_reported=reported,
            raw={"session_id": d.get("session_id"), "cost_usd": d.get("total_cost_usd"), "num_turns": d.get("num_turns")},
        )
