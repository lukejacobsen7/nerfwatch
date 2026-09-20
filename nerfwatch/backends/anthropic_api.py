"""Anthropic Messages API (API key, not subscription). No logprobs are exposed,
so the identity layer is skipped; capability + delivery still work and
`thinking` token counts come back in usage when extended thinking is on.

Target fields: model, api_key_env (default ANTHROPIC_API_KEY), thinking_budget (int, optional).
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from .base import Backend, Response


class AnthropicBackend(Backend):
    name = "anthropic"

    def complete(self, prompt: str) -> Response:
        key = os.environ.get(self.target.get("api_key_env") or "ANTHROPIC_API_KEY", "")
        body: dict = {"model": self.model, "max_tokens": 4096, "messages": [{"role": "user", "content": prompt}]}
        if self.target.get("thinking_budget"):
            body["thinking"] = {"type": "enabled", "budget_tokens": int(self.target["thinking_budget"])}
            body["max_tokens"] = int(self.target["thinking_budget"]) + 4096
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"},
            method="POST",
        )
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                d = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            return Response(text="", latency_ms=0, error=f"HTTP {e.code}: {e.read()[:200]!r}")
        except Exception as e:  # noqa: BLE001
            return Response(text="", latency_ms=0, error=f"{type(e).__name__}: {e}")
        ms = (time.perf_counter() - t0) * 1000
        text = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
        thinking_chars = sum(len(b.get("thinking", "")) for b in d.get("content", []) if b.get("type") == "thinking")
        usage = d.get("usage") or {}
        return Response(
            text=text,
            latency_ms=ms,
            output_tokens=usage.get("output_tokens"),
            # Anthropic doesn't split thinking tokens out of output_tokens; chars/4 is a usable proxy
            reasoning_tokens=(thinking_chars // 4) if thinking_chars else None,
            model_reported=d.get("model"),
            raw={"stop_reason": d.get("stop_reason")},
        )
