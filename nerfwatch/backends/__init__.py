from __future__ import annotations

import shutil
from typing import Any

from .anthropic_api import AnthropicBackend
from .base import Backend, LogprobProbe, Response
from .claude_code import ClaudeCodeBackend
from .codex import CodexBackend
from .gemini_cli import GeminiCliBackend
from .openai_compat import OpenAICompatBackend

REGISTRY: dict[str, type[Backend]] = {
    ClaudeCodeBackend.name: ClaudeCodeBackend,
    CodexBackend.name: CodexBackend,
    GeminiCliBackend.name: GeminiCliBackend,
    OpenAICompatBackend.name: OpenAICompatBackend,
    AnthropicBackend.name: AnthropicBackend,
}


def make(target: dict[str, Any], timeout_s: int = 180) -> Backend:
    try:
        cls = REGISTRY[target["backend"]]
    except KeyError:
        raise SystemExit(f"unknown backend {target['backend']!r}; known: {', '.join(REGISTRY)}") from None
    return cls(target, timeout_s=timeout_s)


def detect_targets() -> list[dict[str, Any]]:
    """Guess sensible targets from what's installed. Used by `nerfwatch init`."""
    import os

    found: list[dict[str, Any]] = []
    if shutil.which("claude"):
        found.append({"name": "claude-code", "backend": "claude-code", "model": None, "enabled": True})
    if shutil.which("codex"):
        found.append({"name": "codex", "backend": "codex", "model": None, "enabled": True})
    if shutil.which("gemini"):
        found.append({"name": "gemini-cli", "backend": "gemini-cli", "model": None, "enabled": False})
    if os.environ.get("OPENAI_API_KEY"):
        found.append({"name": "openai", "backend": "openai-compatible", "model": "gpt-5.6", "api_key_env": "OPENAI_API_KEY", "enabled": True})
    if os.environ.get("ANTHROPIC_API_KEY"):
        found.append({"name": "anthropic-api", "backend": "anthropic", "model": "claude-sonnet-5", "api_key_env": "ANTHROPIC_API_KEY", "enabled": True})
    return found


__all__ = ["Backend", "Response", "LogprobProbe", "REGISTRY", "make", "detect_targets"]
