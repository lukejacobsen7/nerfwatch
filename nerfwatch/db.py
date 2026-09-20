"""SQLite store. One file, three tables, no ORM."""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from typing import Any, Iterator

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY,
  ts REAL NOT NULL,
  target TEXT NOT NULL,
  backend TEXT NOT NULL,
  model_requested TEXT,
  model_reported TEXT,
  suite_hash TEXT NOT NULL,
  n_items INTEGER NOT NULL,
  quick INTEGER NOT NULL DEFAULT 0,
  meta TEXT
);
CREATE TABLE IF NOT EXISTS results (
  id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  item_hash TEXT NOT NULL,
  family TEXT NOT NULL,
  level INTEGER NOT NULL,
  difficulty REAL NOT NULL,
  score REAL,
  latency_ms REAL,
  ttft_ms REAL,
  output_tokens INTEGER,
  reasoning_tokens INTEGER,
  output_chars INTEGER,
  refused INTEGER NOT NULL DEFAULT 0,
  lazy INTEGER NOT NULL DEFAULT 0,
  error TEXT,
  response TEXT
);
CREATE TABLE IF NOT EXISTS identity (
  id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  probe_hash TEXT NOT NULL,
  top_token TEXT,
  top_logprob REAL,
  top5 TEXT,
  system_fingerprint TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs_target ON runs(target, ts);
CREATE INDEX IF NOT EXISTS idx_results_run ON results(run_id);
CREATE INDEX IF NOT EXISTS idx_identity_run ON identity(run_id);
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    con = sqlite3.connect(config.db_path())
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript(SCHEMA)
    try:
        yield con
        con.commit()
    finally:
        con.close()


def new_run(con: sqlite3.Connection, target: dict[str, Any], suite_hash: str, n_items: int, quick: bool) -> int:
    cur = con.execute(
        "INSERT INTO runs(ts,target,backend,model_requested,suite_hash,n_items,quick) VALUES(?,?,?,?,?,?,?)",
        (time.time(), target["name"], target["backend"], target.get("model"), suite_hash, n_items, int(quick)),
    )
    return int(cur.lastrowid)


def finish_run(con: sqlite3.Connection, run_id: int, model_reported: str | None, meta: dict[str, Any]) -> None:
    con.execute("UPDATE runs SET model_reported=?, meta=? WHERE id=?", (model_reported, json.dumps(meta), run_id))


def add_result(con: sqlite3.Connection, run_id: int, r: dict[str, Any]) -> None:
    con.execute(
        """INSERT INTO results(run_id,item_hash,family,level,difficulty,score,latency_ms,ttft_ms,output_tokens,
           reasoning_tokens,output_chars,refused,lazy,error,response)
           VALUES(:run_id,:item_hash,:family,:level,:difficulty,:score,:latency_ms,:ttft_ms,:output_tokens,
           :reasoning_tokens,:output_chars,:refused,:lazy,:error,:response)""",
        {"run_id": run_id, **r},
    )


def add_identity(con: sqlite3.Connection, run_id: int, rows: list[dict[str, Any]]) -> None:
    con.executemany(
        "INSERT INTO identity(run_id,probe_hash,top_token,top_logprob,top5,system_fingerprint) VALUES(?,?,?,?,?,?)",
        [(run_id, r["probe_hash"], r["top_token"], r["top_logprob"], json.dumps(r["top5"]), r.get("system_fingerprint")) for r in rows],
    )


def runs_for(con: sqlite3.Connection, target: str) -> list[sqlite3.Row]:
    return list(con.execute("SELECT * FROM runs WHERE target=? ORDER BY ts", (target,)))


def results_for_run(con: sqlite3.Connection, run_id: int) -> list[sqlite3.Row]:
    return list(con.execute("SELECT * FROM results WHERE run_id=?", (run_id,)))


def identity_for_run(con: sqlite3.Connection, run_id: int) -> list[sqlite3.Row]:
    return list(con.execute("SELECT * FROM identity WHERE run_id=?", (run_id,)))


def targets_seen(con: sqlite3.Connection) -> list[str]:
    return [r[0] for r in con.execute("SELECT DISTINCT target FROM runs ORDER BY target")]
