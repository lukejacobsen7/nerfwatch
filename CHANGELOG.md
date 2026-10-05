# Changelog

## Unreleased

### Probes
- 3 new procedural families aimed at the top of the ladder, where frontier models were scoring 96–99% on levels 3–7 and drift was invisible:
  - `knights`: knights-and-knaves puzzles (3–11 people) with exactly one consistent assignment; claim types grow from same/different kind to "both knaves", "at least one", counting and conditionals
  - `trace`: hand-simulate a short Python loop of modular updates (2–4 variables, 3–32 iterations, up to 2 if/else branches) and give what it prints
  - `chars`: positional edits (swap, insert, delete, reverse span, rotate, replace, duplicate) on a random letter string, which the tokenizer hides
- All three: seeded like the rest (`sha256(salt · period · family · index)`), max level 9, exact grading (set / integer / string), no LLM judge, wired into Rasch θ
- A full run is now 50 calls per target (was 35); `--quick` is 10 (was 7)
- `report` / `dashboard` restart the baseline at the first run with the current family mix, so adding families can't read as a nerf. Existing histories show "building baseline" again for 5 runs after upgrading

### Packaging
- PyPI-ready metadata: SPDX license, full classifiers, project URLs, README as long description (absolute image/link URLs so it renders on PyPI), version read from `nerfwatch.__version__`
- `MANIFEST.in`: sdist ships tests, changelog and contributing docs, not the image assets
- CI: `package` job runs `python -m build`, `twine check --strict`, and installs the wheel into a clean venv to confirm zero runtime dependencies
- `release.yml`: on a `v*` tag, checks the tag matches the version, runs tests, builds, and publishes to PyPI via trusted publishing (OIDC, no stored token)

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
