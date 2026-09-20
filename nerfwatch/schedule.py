"""Install a recurring run: launchd on macOS, crontab elsewhere.

Each firing sleeps a random 0..jitter seconds first, so probes land at
different minutes and you can see time-of-day effects instead of always
hitting the same load window.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from . import config

LABEL = "com.nerfwatch.run"


def _bin() -> str:
    b = shutil.which("nerfwatch")
    if b:
        return b
    return f"{sys.executable} -m nerfwatch.cli"


def _cmd(jitter_s: int, extra: str) -> str:
    logs = config.home() / "logs"
    logs.mkdir(exist_ok=True)
    return f"sleep $((RANDOM % {max(1, jitter_s)})); {_bin()} run {extra} >> {logs}/run.log 2>&1"


def install(every_hours: float, jitter_s: int = 1800, extra: str = "") -> str:
    if platform.system() == "Darwin":
        plist = Path.home() / "Library/LaunchAgents" / f"{LABEL}.plist"
        plist.parent.mkdir(parents=True, exist_ok=True)
        path_env = os.environ.get("PATH", "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin")
        home = os.environ.get("HOME", str(Path.home()))
        plist.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{LABEL}</string>
  <key>ProgramArguments</key><array><string>/bin/sh</string><string>-c</string><string>{_cmd(jitter_s, extra)}</string></array>
  <key>StartInterval</key><integer>{int(every_hours * 3600)}</integer>
  <key>RunAtLoad</key><false/>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>{path_env}</string><key>HOME</key><string>{home}</string></dict>
  <key>StandardOutPath</key><string>{config.home()}/logs/launchd.out</string>
  <key>StandardErrorPath</key><string>{config.home()}/logs/launchd.err</string>
</dict></plist>
""")
        subprocess.run(["launchctl", "unload", str(plist)], capture_output=True)
        r = subprocess.run(["launchctl", "load", str(plist)], capture_output=True, text=True)
        if r.returncode != 0:
            return f"launchctl load failed: {r.stderr.strip()}"
        return f"installed launchd job {LABEL}: every {every_hours:g}h (+0-{jitter_s//60}min jitter) → {plist}"
    # cron
    minutes = int(every_hours * 60)
    spec = f"*/{minutes} * * * *" if minutes < 60 else f"0 */{int(every_hours)} * * *"
    line = f"{spec} {_cmd(jitter_s, extra)}  # nerfwatch"
    cur = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
    keep = [l for l in cur.splitlines() if "# nerfwatch" not in l]
    new = "\n".join(keep + [line]) + "\n"
    subprocess.run(["crontab", "-"], input=new, text=True, check=True)
    return f"installed cron entry: {spec}"


def remove() -> str:
    if platform.system() == "Darwin":
        plist = Path.home() / "Library/LaunchAgents" / f"{LABEL}.plist"
        if plist.exists():
            subprocess.run(["launchctl", "unload", str(plist)], capture_output=True)
            plist.unlink()
            return f"removed {plist}"
        return "no launchd job installed"
    cur = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
    keep = [l for l in cur.splitlines() if "# nerfwatch" not in l]
    subprocess.run(["crontab", "-"], input="\n".join(keep) + "\n", text=True)
    return "removed cron entry"


def status() -> str:
    if platform.system() == "Darwin":
        r = subprocess.run(["launchctl", "list", LABEL], capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else "not scheduled"
    cur = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
    lines = [l for l in cur.splitlines() if "# nerfwatch" in l]
    return "\n".join(lines) if lines else "not scheduled"
