"""OpenAI Codex CLI (ChatGPT subscription). `codex exec --json` streams JSONL.

The `turn.completed` event carries `reasoning_output_tokens`: the closest thing
to a public "how much juice did I get" meter on a subscription. Track it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .base import Backend, Response, run_cli


def _default_model() -> str | None:
    """codex exec doesn't echo the model it used; read the user's config.toml."""
    try:
        for line in (Path.home() / ".codex" / "config.toml").read_text().splitlines():
            m = re.match(r'\s*model\s*=\s*"([^"]+)"', line)
            if m:
                return m.group(1)
    except OSError:
        pass
    return None


class CodexBackend(Backend):
    name = "codex"

    def complete(self, prompt: str) -> Response:
        argv = ["codex", "exec", "--json", "--skip-git-repo-check", "--ephemeral", "-s", "read-only"]
        if self.model:
            argv += ["-m", self.model]
        if self.target.get("effort"):
            argv += ["-c", f'model_reasoning_effort="{self.target["effort"]}"']
        argv.append(prompt)
        out, err, rc, wall = run_cli(argv, self.timeout_s)
        text_parts: list[str] = []
        usage: dict = {}
        error = None
        for line in out.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                ev = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            t = ev.get("type")
            if t == "item.completed" and (ev.get("item") or {}).get("type") == "agent_message":
                text_parts.append(ev["item"].get("text") or "")
            elif t == "turn.completed":
                usage = ev.get("usage") or {}
            elif t in ("turn.failed", "error"):
                error = json.dumps(ev)[:200]
        if not text_parts and error is None and rc != 0:
            error = f"rc={rc}: {(err or out)[:200]}"
        return Response(
            text="\n".join(text_parts),
            latency_ms=wall,
            output_tokens=usage.get("output_tokens"),
            reasoning_tokens=usage.get("reasoning_output_tokens"),
            model_reported=self.model or _default_model(),
            error=error,
            raw={"usage": usage},
        )
