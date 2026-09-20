# Changelog

## 0.1.0 — 2026-09-19

Initial release.

- Backends: `claude-code`, `codex`, `gemini-cli` (untested), `openai-compatible`, `anthropic`
- 7 procedural probe families with deterministic graders on a 9-level ladder; adaptive 5-level window per run
- Rasch (1-PL) ability estimate, bootstrap CIs
- Two-sided CUSUM alarms with 2-run confirmation; plain-English verdict
- Identity layer: single-token logprob probes (mean top-5 logprob + top-token agreement)
- Terminal report, single-file HTML dashboard, `serve`, CSV export
- `schedule`: launchd on macOS, crontab elsewhere, with random jitter
- Validated: a silent Ollama model swap (qcoder → Gemma) tripped the identity alarm on the exact run of the swap
