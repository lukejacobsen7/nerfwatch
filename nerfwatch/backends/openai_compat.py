"""Any OpenAI-compatible chat endpoint: api.openai.com, Ollama, OpenRouter,
NVIDIA NIM, vLLM, LM Studio, Groq, xAI, Together...

Target fields:
  base_url   e.g. https://api.openai.com/v1  (default) or http://localhost:11434/v1
  api_key_env  name of env var holding the key (default OPENAI_API_KEY)
  model
  effort     optional reasoning_effort (minimal|low|medium|high)

Identity layer: 1-token completion with logprobs + top_logprobs=5. This is the
Log Probability Tracking method (arXiv 2512.03816): the mean top-token logprob
across a fixed prompt set shifts when the served weights / quantization /
inference stack shift, and it costs ~nothing.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from .base import Backend, LogprobProbe, Response


class OpenAICompatBackend(Backend):
    name = "openai-compatible"
    supports_logprobs = True

    def _post(self, body: dict) -> tuple[dict, float]:
        base = (self.target.get("base_url") or "https://api.openai.com/v1").rstrip("/")
        key = os.environ.get(self.target.get("api_key_env") or "OPENAI_API_KEY", "")
        req = urllib.request.Request(
            base + "/chat/completions",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {key}"} if key else {})},
            method="POST",
        )
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            d = json.loads(resp.read().decode())
        return d, (time.perf_counter() - t0) * 1000

    def complete(self, prompt: str) -> Response:
        body: dict = {"model": self.model, "messages": [{"role": "user", "content": prompt}]}
        if self.target.get("effort"):
            body["reasoning_effort"] = self.target["effort"]
        if self.target.get("temperature") is not None:
            body["temperature"] = self.target["temperature"]
        try:
            d, ms = self._post(body)
        except urllib.error.HTTPError as e:
            return Response(text="", latency_ms=0, error=f"HTTP {e.code}: {e.read()[:200]!r}")
        except Exception as e:  # noqa: BLE001
            return Response(text="", latency_ms=0, error=f"{type(e).__name__}: {e}")
        if "choices" not in d:
            return Response(text="", latency_ms=ms, error=json.dumps(d)[:200])
        ch = d["choices"][0]
        msg = ch.get("message") or {}
        text = msg.get("content") or ""
        usage = d.get("usage") or {}
        details = usage.get("completion_tokens_details") or {}
        return Response(
            text=text,
            latency_ms=ms,
            output_tokens=usage.get("completion_tokens"),
            reasoning_tokens=details.get("reasoning_tokens"),
            model_reported=d.get("model"),
            raw={"system_fingerprint": d.get("system_fingerprint"), "finish_reason": ch.get("finish_reason")},
        )

    def logprob_probe(self, prompt: str) -> LogprobProbe | None:
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1,
            "temperature": 0,
            "logprobs": True,
            "top_logprobs": 5,
        }
        try:
            d, _ = self._post(body)
        except Exception:  # noqa: BLE001
            return None
        try:
            lp = d["choices"][0]["logprobs"]["content"][0]
        except (KeyError, IndexError, TypeError):
            return None
        top5 = [(t["token"], float(t["logprob"])) for t in (lp.get("top_logprobs") or [])][:5]
        return LogprobProbe(top_token=lp["token"], top_logprob=float(lp["logprob"]), top5=top5, system_fingerprint=d.get("system_fingerprint"))
