# nerfwatch

**Is your model getting dumber? Measure it instead of arguing about it.**

`nerfwatch` runs a private, procedurally generated probe suite against the models you actually use, on a schedule, from your own machine, and tells you when something *sustainably* shifted: ability, speed, reasoning budget, laziness, refusals, or the served weights themselves.

- **Works on subscriptions.** Points at the `claude` and `codex` CLIs you already pay for. No API key needed. (Also any OpenAI-compatible endpoint: OpenAI, Ollama, OpenRouter, NIM, vLLM, Groq, xAI... and the Anthropic API.)
- **Zero dependencies.** Python stdlib only. `uv tool install` and it's there.
- **Local.** SQLite in `~/.nerfwatch/`. Nothing leaves your machine.
- **No LLM judge.** Every probe has a deterministic grader.
- **Not vibes.** Alarms come from CUSUM change detection over a baseline, with a two-run confirmation rule.

```
== codex ==  14 runs, last 2026-09-19 21:07
   model reported: gpt-6-astra
   metric                             baseline       last  trend
   ability θ (Rasch)                     +1.62      +0.71  ↓!  ⚠ down
   accuracy                                91%        74%  ↓!  ⚠ down
   latency ms (median)                    8712       5104  ↓
   reasoning tokens (median)               418         61      ⚠ down
   output tokens (median)                   92         88
   refusal rate                             0%         0%  =
   lazy rate (effort probes)                0%        40%  ↑!  ⚠ up
   ...
   verdict: REASONING BUDGET CUT: fewer reasoning tokens and lower ability, identity stable. Same weights, less compute; laziness up: effort probes are being skipped/summarized
```
*(illustrative output)*

## Install

```bash
uv tool install git+https://github.com/lukejacobsen7/nerfwatch   # or pipx / pip
nerfwatch init        # private salt + auto-detect claude / codex / gemini / API keys
nerfwatch doctor      # one ping per target
nerfwatch run --quick # 7 calls per target, first data point
nerfwatch schedule --every 6   # launchd (macOS) or cron: full suite every 6h + random jitter
nerfwatch dashboard   # HTML, opens in your browser
```

Hand this repo to Claude Code / Codex and say "install it": `AGENTS.md` has the exact steps.

## What it measures, and why each thing is there

Complaints that a model "got worse" conflate three different things. nerfwatch separates them so the verdict can say *which* one happened.

| Layer | Question | Signal | Method |
|---|---|---|---|
| **Identity** | Did the thing behind the endpoint change? | 1-token completions with `logprobs`, fixed prompt set | Log-probability tracking ([arXiv 2512.03816](https://arxiv.org/abs/2512.03816)): mean top-5 logprob + top-token agreement. Detects new weights, quantization, inference-stack swaps. API backends only. |
| **Capability** | Did it get dumber? | 7 probe families × 5 difficulty levels, regenerated weekly from your private salt | Rasch (1-PL IRT) ability **θ** so runs stay comparable when items rotate; raw accuracy; per-family accuracy. |
| **Delivery** | Did it get slower, lazier, stingier? | latency, `reasoning_tokens` (Codex, OpenAI, Claude thinking), output tokens, refusal rate on benign prompts, "lazy" rate on long enumeration tasks | Medians per run. **Reasoning tokens are the "juice" meter**: when a provider quietly lowers reasoning effort, the weights don't change but this number does. |

Every metric series gets a two-sided **CUSUM** (Page 1954): baseline = first 5 runs, k = 0.5σ, h = 4σ, alarm only when the statistic stays over threshold for 2 consecutive runs. Heavy-tailed series (latency, tokens) are tracked on log scale.

The verdict combines alarms:

| Identity | θ / accuracy | Reasoning tokens | Verdict |
|---|---|---|---|
| shifted | down | – | **the model changed and got worse** (new weights / quant / stack) |
| stable | down | down | **reasoning budget cut** (same weights, less compute) |
| stable | down | stable | ability dropped, cause unclear |
| – | stable | – | stable / slower-not-dumber / lazier / more refusals, as applicable |

### Probe families

| Family | What | Difficulty knob |
|---|---|---|
| `arith` | multi-step integer arithmetic | digits × operations |
| `logic` | transitive-relation puzzles ("who is tallest?") with distractors | chain length |
| `listops` | apply k list transformations in order | k |
| `code` | write a Python function; hidden tests run in a subprocess | composition depth |
| `instruct` | satisfy N simultaneous formatting constraints | N |
| `effort` | enumerate 27–75 required lines; skipping or "..." = fail | line count |
| `refusal` | benign questions with scary words ("how do I kill a Python process") | – |

Items are generated from `sha256(salt · period · family · index)`. The salt is created at `init` and never shared, so your suite can't be trained on. Rotation is weekly by default (`"rotation": "frozen" | "weekly" | "daily"` in config).

## Cost on a subscription

A full run is 35 calls per target (+24 tiny logprob calls on API targets). `--every 6` = 140 calls/day/target. Each `claude -p` call re-sends its system prompt, which counts toward your rate limit but not your bill. Use `--every 12`, `--quick` (7 calls), or set `items_per_family` lower in config to trim.

## Commands

```
nerfwatch init [--redetect]           config + salt + auto-detect targets
nerfwatch add --name X --backend B    add a target (see backends below)
nerfwatch remove | enable | disable   manage targets
nerfwatch targets                     list targets and run counts
nerfwatch doctor [-t X]               liveness + logprob check
nerfwatch run [-t X] [--quick]        run the suite now, print report
nerfwatch report [-t X] [--json]      metrics, alarms, verdict
nerfwatch dashboard [--out F]         write + open the HTML dashboard
nerfwatch serve [--port 8787]         live dashboard on localhost
nerfwatch schedule --every H          install launchd/cron job (--remove, --status)
nerfwatch export                      every result as CSV
nerfwatch show [--run ID] [--quick]   print this period's prompts, or a run's responses
```

### Backends

| `--backend` | Needs | Identity layer | Reasoning tokens |
|---|---|---|---|
| `claude-code` | `claude` CLI, logged in | no | thinking tokens |
| `codex` | `codex` CLI, logged in | no | `reasoning_output_tokens` |
| `gemini-cli` | `gemini` CLI | no | no (untested; see file) |
| `openai-compatible` | `--base-url`, `--api-key-env` | yes, if the endpoint returns `logprobs` | `reasoning_tokens` when returned |
| `anthropic` | `ANTHROPIC_API_KEY` | no | thinking (chars/4 proxy) |

```bash
nerfwatch add --name codex-astra --backend codex --model gpt-6-astra --effort high
nerfwatch add --name opus --backend claude-code --model opus
nerfwatch add --name ollama --backend openai-compatible --base-url http://localhost:11434/v1 --model llama3.3
nerfwatch add --name or-kimi --backend openai-compatible --base-url https://openrouter.ai/api/v1 --api-key-env OPENROUTER_API_KEY --model moonshotai/kimi-k3
```

## Caveats, honestly

- **Rasch difficulties are design-calibrated**, one logit per level, not fitted across 100+ models. θ is comparable across *your* runs of *one* target; don't compare θ across targets like a leaderboard.
- **Identity only works where logprobs are exposed.** The CLIs don't expose them. For subscriptions you get capability + delivery, which is still enough to tell "reasoning budget cut" from "generally worse".
- **5 runs of baseline are required** before any verdict. If the model was already nerfed when you started, your baseline is the nerfed state.
- **Sampling noise is real.** 35 items → accuracy has ±8% sampling error per run. That is exactly why the alarms are CUSUM over runs and not a threshold on one run.
- `claude -p` counts toward your plan's limits.

## Prior art

[Chen, Zaharia, Zou 2023](https://arxiv.org/abs/2307.09009) showed GPT-4 drift first. [daily-bench](https://github.com/jacobphillips99/daily-bench) and [model-drift](https://github.com/egnaro9/model-drift) are public dashboards for the models their authors pay for. nerfwatch is the installable version for the models *you* pay for, with an identity layer from [Log Probability Tracking](https://arxiv.org/abs/2512.03816) and difficulty-aware scoring.

MIT.
