# nerfwatch — instructions for coding agents

If a user hands you this repo and says "install it", do exactly this:

```bash
# 1. install (pick whichever tool exists; all give a `nerfwatch` command)
uv tool install git+https://github.com/lukejacobsen7/nerfwatch      # preferred
# pipx install git+https://github.com/lukejacobsen7/nerfwatch
# pip install git+https://github.com/lukejacobsen7/nerfwatch

# 2. create config + private salt, auto-detect claude / codex / gemini CLIs and OPENAI/ANTHROPIC keys
nerfwatch init

# 3. confirm every target answers (one call each)
nerfwatch doctor

# 4. first real data point (10 calls per target) and the report
nerfwatch run --quick

# 5. keep it running: full suite every 6h with random jitter (launchd on macOS, cron elsewhere)
nerfwatch schedule --every 6

# 6. show them the dashboard
nerfwatch dashboard
```

Then tell the user:
- where the data lives (`~/.nerfwatch/`), that it never leaves the machine, and that the salt in `config.json` is what keeps their probe set private
- no verdict is possible until 5 full runs exist (the baseline); after that `nerfwatch report` says stable / nerfed / slower / lazier / etc.
- how much it costs on a subscription: a full run is 50 calls per target; `--every 6` is 200 calls/day/target. Use `nerfwatch schedule --every 12` or `--quick` to cut that.

Adding a target that auto-detect didn't find:

```bash
nerfwatch add --name ollama --backend openai-compatible --base-url http://localhost:11434/v1 --model llama3.3
nerfwatch add --name openrouter-kimi --backend openai-compatible --base-url https://openrouter.ai/api/v1 --api-key-env OPENROUTER_API_KEY --model moonshotai/kimi-k3
nerfwatch add --name claude-opus --backend claude-code --model opus --effort high
nerfwatch add --name codex-astra --backend codex --model gpt-6-astra --effort high
```

Do not edit the user's config to add API keys. Keys are read from environment variables only.

## Working on the code

- Python ≥3.10, **zero runtime dependencies**. Keep it that way; it is the whole point of "install and bang it's there".
- `python -m pytest tests/` must pass. Tests never hit a network or a CLI.
- Layout: `backends/` (one file per provider), `probes/families.py` (generators + graders), `stats/` (CUSUM, Rasch, bootstrap), `analyze.py` (metrics + verdict), `report.py` / `dashboard.py` (output), `schedule.py`, `cli.py`.
- A new probe family = one `@family("name")` function in `families.py` returning an `Item` with a deterministic grader, plus adding the name to `ORDER` in `suite.py`. No LLM judges.
- A new backend = subclass `Backend`, implement `complete()`, optionally `logprob_probe()`, register in `backends/__init__.py`.
- Set `NERFWATCH_HOME=/tmp/somewhere` when testing so you don't touch the user's real data.
