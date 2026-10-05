# Contributing

Thanks for looking. The bar is simple: keep it installable, keep it honest.

## Ground rules

- **Zero runtime dependencies.** Python stdlib only. If a feature needs a package, it needs a very good reason.
- **No LLM judges.** Every probe is graded by code that returns the same score every time.
- **Tests don't touch the network or a CLI.** `python -m pytest tests/` must pass offline.
- **Don't leak the salt.** Never log or print `config["salt"]`; it's what keeps a user's probe set private.

## Dev setup

```bash
git clone https://github.com/lukejacobsen7/nerfwatch && cd nerfwatch
uv tool install -e .            # or: pip install -e .
export NERFWATCH_HOME=/tmp/nw   # keep your real data untouched while hacking
nerfwatch init && nerfwatch show --quick
python -m pytest tests/ -q
```

## Adding a probe family

1. Write a `@family("name")` function in `nerfwatch/probes/families.py` that takes `(rng, level)` and returns an `Item` with a `grade(item, response) -> float` closure.
2. Make sure `grade(item, <the reference answer>) == 1.0` and a wrong answer scores `< 1.0`; `tests/test_probes.py` does this automatically for the families it knows, so extend `_ref_response`.
3. Add the name to `ORDER` in `probes/suite.py` and its ceiling to `FAMILY_MAX_LEVEL`.
4. Difficulty must actually rise with `level` (that's what Rasch assumes).

## Adding a backend

Subclass `Backend` in `nerfwatch/backends/`, implement `complete(prompt) -> Response`, optionally `logprob_probe(prompt) -> LogprobProbe`, and register it in `backends/__init__.py`. Include a docstring with the exact headless command and the JSON shape you parsed.

## Releasing

1. Bump `__version__` in `nerfwatch/__init__.py` and move the `Unreleased` entries in `CHANGELOG.md` under that version.
2. Check locally: `python -m build && python -m twine check --strict dist/*`.
3. Merge, then tag `vX.Y.Z` on `main` and push the tag. `.github/workflows/release.yml` refuses a tag that doesn't match `__version__`, then publishes via PyPI trusted publishing.

One-time setup (maintainer): on pypi.org add a trusted publisher for `lukejacobsen7/nerfwatch`, workflow `release.yml`, environment `pypi`, and create a `pypi` environment in the repo settings (optionally with required reviewers).

## Reporting a nerf

If nerfwatch caught something real, open a discussion with `nerfwatch report --json` output (it contains no prompts). That's the most useful contribution there is.
