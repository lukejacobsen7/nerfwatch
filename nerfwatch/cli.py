"""nerfwatch CLI. `nerfwatch --help`."""

from __future__ import annotations

import argparse
import csv
import http.server
import json
import sys
import webbrowser
from pathlib import Path

from . import __version__, backends, config, db, schedule
from .analyze import analyze
from .report import report


def _targets(cfg: dict, names: list[str] | None, enabled_only: bool = True) -> list[dict]:
    ts = cfg.get("targets", [])
    if names:
        missing = [n for n in names if not config.target_by_name(cfg, n)]
        if missing:
            raise SystemExit(f"unknown target(s): {', '.join(missing)}. run `nerfwatch targets`")
        return [t for t in ts if t["name"] in names]
    return [t for t in ts if t.get("enabled", True)] if enabled_only else ts


def cmd_init(a: argparse.Namespace) -> None:
    cfg = config.ensure_salt(config.load())
    if not cfg.get("targets") or a.redetect:
        found = backends.detect_targets()
        existing = {t["name"] for t in cfg.get("targets", [])}
        cfg["targets"] = cfg.get("targets", []) + [t for t in found if t["name"] not in existing]
    config.save(cfg)
    print(f"config: {config.config_path()}")
    print(f"db:     {config.db_path()}")
    if cfg["targets"]:
        print("targets:")
        for t in cfg["targets"]:
            print(f"  {'[x]' if t.get('enabled', True) else '[ ]'} {t['name']:16} {t['backend']:18} {t.get('model') or '(default model)'}")
    else:
        print("no targets detected. add one: nerfwatch add --name ollama --backend openai-compatible --base-url http://localhost:11434/v1 --model llama3")
    print("next: nerfwatch doctor && nerfwatch run --quick && nerfwatch schedule --every 6")


def cmd_add(a: argparse.Namespace) -> None:
    cfg = config.ensure_salt(config.load())
    if config.target_by_name(cfg, a.name):
        raise SystemExit(f"target {a.name!r} already exists (nerfwatch remove {a.name} first)")
    t = {"name": a.name, "backend": a.backend, "model": a.model, "enabled": True}
    for k in ("base_url", "api_key_env", "effort", "thinking_budget"):
        v = getattr(a, k, None)
        if v is not None:
            t[k] = v
    if a.temperature is not None:
        t["temperature"] = a.temperature
    cfg["targets"].append(t)
    config.save(cfg)
    print(f"added {a.name}: {json.dumps(t)}")


def cmd_remove(a: argparse.Namespace) -> None:
    cfg = config.load()
    n = len(cfg["targets"])
    cfg["targets"] = [t for t in cfg["targets"] if t["name"] != a.name]
    if len(cfg["targets"]) == n:
        raise SystemExit(f"no target {a.name!r}")
    config.save(cfg)
    print(f"removed {a.name} (its stored runs are kept)")


def cmd_enable(a: argparse.Namespace, on: bool) -> None:
    cfg = config.load()
    t = config.target_by_name(cfg, a.name)
    if not t:
        raise SystemExit(f"no target {a.name!r}")
    t["enabled"] = on
    config.save(cfg)
    print(f"{a.name}: {'enabled' if on else 'disabled'}")


def cmd_targets(a: argparse.Namespace) -> None:
    cfg = config.load()
    if not cfg.get("targets"):
        print("no targets. run `nerfwatch init` or `nerfwatch add ...`")
        return
    with db.connect() as con:
        for t in cfg["targets"]:
            n = len(db.runs_for(con, t["name"]))
            print(f"{'[x]' if t.get('enabled', True) else '[ ]'} {t['name']:16} {t['backend']:18} {t.get('model') or '(default)':28} {n} runs")


def cmd_doctor(a: argparse.Namespace) -> None:
    cfg = config.load()
    bad = 0
    for t in _targets(cfg, a.target, enabled_only=False):
        be = backends.make(t, timeout_s=int(cfg.get("request_timeout_s", 180)))
        ok, msg = be.doctor()
        lp = ""
        if ok and be.supports_logprobs:
            p = be.logprob_probe("The capital of France is")
            lp = " · logprobs: " + ("yes" if p else "NO (identity layer will be skipped)")
        print(f"{'OK ' if ok else 'ERR'} {t['name']:16} {msg}{lp}")
        bad += not ok
    sys.exit(1 if bad else 0)


def cmd_run(a: argparse.Namespace) -> None:
    from .runner import run_target

    cfg = config.load()
    if not cfg.get("salt"):
        raise SystemExit("run `nerfwatch init` first")
    ts = _targets(cfg, a.target)
    if not ts:
        raise SystemExit("no enabled targets")
    for t in ts:
        try:
            run_target(cfg, t, quick=a.quick, parallel=a.parallel)
        except KeyboardInterrupt:
            raise
        except Exception as e:  # noqa: BLE001
            print(f"[{t['name']}] FAILED: {type(e).__name__}: {e}", file=sys.stderr)
    if not a.no_report:
        print()
        print(report(cfg, [t["name"] for t in ts]))


def _seen_targets(cfg: dict, names: list[str] | None) -> list[str]:
    if names:
        return names
    with db.connect() as con:
        seen = db.targets_seen(con)
    order = [t["name"] for t in cfg.get("targets", [])]
    return sorted(seen, key=lambda n: (order.index(n) if n in order else 99, n))


def cmd_report(a: argparse.Namespace) -> None:
    cfg = config.load()
    names = _seen_targets(cfg, a.target)
    if not names:
        print("no runs yet")
        return
    if a.json:
        out = []
        for n in names:
            ta = analyze(n, cfg)
            out.append({"target": n, "verdict": ta.verdict, "alarms": ta.alarms, "runs": [vars(m) for m in ta.runs]})
        print(json.dumps(out, indent=2, default=str))
    else:
        print(report(cfg, names))


def cmd_dashboard(a: argparse.Namespace) -> None:
    from . import dashboard

    cfg = config.load()
    p = dashboard.write(cfg, _seen_targets(cfg, a.target), Path(a.out) if a.out else None)
    print(p)
    if not a.no_open:
        webbrowser.open(p.as_uri())


def cmd_serve(a: argparse.Namespace) -> None:
    from . import dashboard

    cfg = config.load()

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            p = dashboard.write(cfg, _seen_targets(cfg, None))
            body = p.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # silence
            pass

    print(f"serving http://127.0.0.1:{a.port}  (ctrl-c to stop)")
    http.server.ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()


def cmd_schedule(a: argparse.Namespace) -> None:
    if a.remove:
        print(schedule.remove())
    elif a.status:
        print(schedule.status())
    else:
        extra = "--quick" if a.quick else ""
        print(schedule.install(a.every, jitter_s=int(a.jitter * 60), extra=extra))


def cmd_export(a: argparse.Namespace) -> None:
    with db.connect() as con:
        rows = con.execute(
            "SELECT r.id AS result_id, r.run_id, ru.ts, ru.target, ru.model_reported, ru.suite_hash, r.item_hash, r.family, r.level, r.difficulty, r.score, r.latency_ms, r.ttft_ms, r.output_tokens, r.reasoning_tokens, r.output_chars, r.refused, r.lazy, r.error"
            " FROM results r JOIN runs ru ON ru.id=r.run_id ORDER BY ru.ts, r.id"
        ).fetchall()
    w = csv.writer(sys.stdout)
    if rows:
        w.writerow(rows[0].keys())
        for r in rows:
            w.writerow(list(r))


def cmd_show(a: argparse.Namespace) -> None:
    from .probes import build

    cfg = config.load()
    if a.run:
        with db.connect() as con:
            for r in db.results_for_run(con, a.run):
                print(f"--- {r['family']} L{r['level']} score={r['score']} lat={r['latency_ms']} rt={r['reasoning_tokens']} refused={r['refused']} lazy={r['lazy']} err={r['error']}")
                print((r["response"] or "")[:600])
        return
    items, h = build(cfg["salt"], int(cfg.get("items_per_family", 5)), quick=a.quick, rotation=cfg.get("rotation", "weekly"), center=a.center)
    print(f"suite {h}: {len(items)} items")
    for it in items:
        print(f"--- {it.family} L{it.level} b={it.difficulty:+.0f} {it.hash}\n{it.prompt}\n")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="nerfwatch", description="Is your model getting dumber? Track LLM drift locally.")
    p.add_argument("--version", action="version", version=f"nerfwatch {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="create config, generate your private salt, detect installed CLIs / keys")
    s.add_argument("--redetect", action="store_true", help="re-run auto-detection and append new targets")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("add", help="add a target")
    s.add_argument("--name", required=True)
    s.add_argument("--backend", required=True, choices=sorted(backends.REGISTRY))
    s.add_argument("--model", help="model id (CLI backends: omit for the CLI's default)")
    s.add_argument("--base-url", dest="base_url", help="openai-compatible only, e.g. http://localhost:11434/v1")
    s.add_argument("--api-key-env", dest="api_key_env", help="env var holding the key")
    s.add_argument("--effort", help="reasoning effort, if the backend supports it (low|medium|high...)")
    s.add_argument("--thinking-budget", dest="thinking_budget", type=int, help="anthropic: extended-thinking budget tokens")
    s.add_argument("--temperature", type=float)
    s.set_defaults(fn=cmd_add)

    s = sub.add_parser("remove", help="remove a target (keeps its data)")
    s.add_argument("name")
    s.set_defaults(fn=cmd_remove)
    s = sub.add_parser("enable")
    s.add_argument("name")
    s.set_defaults(fn=lambda a: cmd_enable(a, True))
    s = sub.add_parser("disable")
    s.add_argument("name")
    s.set_defaults(fn=lambda a: cmd_enable(a, False))

    s = sub.add_parser("targets", help="list targets")
    s.set_defaults(fn=cmd_targets)

    s = sub.add_parser("doctor", help="one ping per target; checks logprob support")
    s.add_argument("--target", "-t", action="append")
    s.set_defaults(fn=cmd_doctor)

    s = sub.add_parser("run", help="run the probe suite now")
    s.add_argument("--target", "-t", action="append", help="only these targets (repeatable)")
    s.add_argument("--quick", action="store_true", help="1 item per family (10 calls) instead of the full suite")
    s.add_argument("--parallel", type=int, default=3)
    s.add_argument("--no-report", action="store_true")
    s.set_defaults(fn=cmd_run)

    s = sub.add_parser("report", help="terminal report with CUSUM alarms and a verdict")
    s.add_argument("--target", "-t", action="append")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_report)

    s = sub.add_parser("dashboard", help="write the HTML dashboard and open it")
    s.add_argument("--target", "-t", action="append")
    s.add_argument("--out", help="output path (default ~/.nerfwatch/dashboard.html)")
    s.add_argument("--no-open", action="store_true")
    s.set_defaults(fn=cmd_dashboard)

    s = sub.add_parser("serve", help="serve the live dashboard on localhost")
    s.add_argument("--port", type=int, default=8787)
    s.set_defaults(fn=cmd_serve)

    s = sub.add_parser("schedule", help="install a recurring run (launchd / cron)")
    s.add_argument("--every", type=float, default=6, help="hours between runs (default 6)")
    s.add_argument("--jitter", type=float, default=30, help="random delay in minutes added to each run (default 30)")
    s.add_argument("--quick", action="store_true", help="schedule quick runs instead of full")
    s.add_argument("--remove", action="store_true")
    s.add_argument("--status", action="store_true")
    s.set_defaults(fn=cmd_schedule)

    s = sub.add_parser("export", help="dump every result as CSV to stdout")
    s.set_defaults(fn=cmd_export)

    s = sub.add_parser("show", help="print this period's prompts, or the responses of a run")
    s.add_argument("--run", type=int, help="run id to show responses for")
    s.add_argument("--quick", action="store_true")
    s.add_argument("--center", type=int, default=5, help="centre level of the 5-level window (1-9)")
    s.set_defaults(fn=cmd_show)

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
