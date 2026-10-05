"""The knights / trace / chars families, checked against independent re-implementations
that read the prompt text back, so a generator bug can't grade itself correct."""

import contextlib
import io
import itertools
import random
import re
import statistics

from nerfwatch.analyze import current_suite
from nerfwatch.probes import FAMILIES, ORDER, build
from nerfwatch.probes.families import FAMILY_MAX_LEVEL

HARD = ("knights", "trace", "chars")
SEEDS = range(40)


def _items(fam, level):
    return [FAMILIES[fam](random.Random(s * 1000 + level), level) for s in SEEDS]


def _kk_eval(claim, w):
    c = re.sub(r"^(At|If|Exactly|None)\b", lambda m: m[0].lower(), claim)
    if m := re.fullmatch(r"(\w+) is a (knight|knave)", c):
        return w[m[1]] == (m[2] == "knight")
    if m := re.fullmatch(r"(\w+) and (\w+) are the same kind", c):
        return w[m[1]] == w[m[2]]
    if m := re.fullmatch(r"(\w+) and (\w+) are different kinds", c):
        return w[m[1]] != w[m[2]]
    if m := re.fullmatch(r"(\w+) and (\w+) are both knaves", c):
        return not w[m[1]] and not w[m[2]]
    if m := re.fullmatch(r"at least one of (\w+) and (\w+) is a knight", c):
        return w[m[1]] or w[m[2]]
    if m := re.fullmatch(r"if (\w+) is a knight, then (\w+) is a knave", c):
        return not (w[m[1]] and w[m[2]])
    if m := re.fullmatch(r"(?:exactly (\d+)|(none)) of (.+?) (?:is a knight|are knights)", c):
        who = re.findall(r"[A-Z]\w+", m[3])
        return sum(w[x] for x in who) == (0 if m[2] else int(m[1]))
    raise AssertionError(f"unparsed claim: {claim}")


def test_knights_have_exactly_one_solution_and_it_is_the_key():
    for level in range(1, 10):
        for it in _items("knights", level):
            people = it.meta["people"]
            assert len(people) == level + 2
            claims = re.findall(r'^(\w+) says: "(.+)\."$', it.prompt, re.M)
            assert len(claims) == it.meta["n_claims"]
            sols = []
            for bits in itertools.product((True, False), repeat=len(people)):
                w = dict(zip(people, bits))
                if all(w[sp] == _kk_eval(c, w) for sp, c in claims):
                    sols.append(sorted(p for p in people if w[p]))
            assert sols == [it.key], (level, it.prompt)
            assert it.grade(it, "Knights: " + ", ".join(reversed(it.key))) == 1.0


def test_trace_key_matches_running_the_printed_program():
    for level in range(1, 10):
        for it in _items("trace", level):
            src = re.search(r"```python\n(.*?)```", it.prompt, re.S)[1]
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                exec(src, {})  # noqa: S102 - generated test program
            assert int(buf.getvalue()) == it.key


def _apply_edit(s, step):
    n = r"(\d+)(?:st|nd|rd|th)"
    if m := re.fullmatch(rf"swap the {n} and {n} characters", step):
        i, j = int(m[1]) - 1, int(m[2]) - 1
        t = list(s)
        t[i], t[j] = t[j], t[i]
        return "".join(t)
    if m := re.fullmatch(rf"delete the {n} character", step):
        i = int(m[1]) - 1
        return s[:i] + s[i + 1:]
    if m := re.fullmatch(rf"insert the letter (\w) so that it becomes the {n} character", step):
        i = int(m[2]) - 1
        return s[:i] + m[1] + s[i:]
    if m := re.fullmatch(rf"reverse the characters from the {n} to the {n} inclusive", step):
        i, j = int(m[1]) - 1, int(m[2])
        return s[:i] + s[i:j][::-1] + s[j:]
    if m := re.fullmatch(r"move the first (\d+) characters to the end, keeping their order", step):
        return s[int(m[1]):] + s[: int(m[1])]
    if m := re.fullmatch(r"replace every (\w) with (\w)", step):
        return s.replace(m[1], m[2])
    if m := re.fullmatch(rf"duplicate the {n} character \(it now appears twice in a row\)", step):
        i = int(m[1]) - 1
        return s[:i] + s[i] + s[i:]
    raise AssertionError(f"unparsed edit: {step}")


def test_chars_key_matches_replaying_the_edits():
    for level in range(1, 10):
        for it in _items("chars", level):
            s = re.search(r"string: (\w+)", it.prompt)[1]
            steps = re.findall(r"^\d+\. (.+)$", it.prompt, re.M)
            assert len(steps) == level + 1
            for st in steps:
                s = _apply_edit(s, st)
            assert s == it.key
            assert it.grade(it, f"The final string is `{it.key}`.") == 1.0


def test_hard_families_get_harder_with_level():
    def work(it):
        if it.family == "knights":
            return len(it.meta["people"]) * it.meta["n_claims"]
        if it.family == "trace":
            return it.meta["iters"] * (it.meta["vars"] + it.meta["branches"])
        return len(it.meta["start"]) * len(it.meta["steps"])

    for fam in HARD:
        load = [statistics.mean(work(it) for it in _items(fam, lvl)) for lvl in range(1, 10)]
        assert all(a < b for a, b in zip(load, load[1:])), (fam, load)


def test_hard_families_are_in_the_suite_seeded_like_the_rest():
    assert all(f in ORDER and FAMILY_MAX_LEVEL[f] == 9 for f in HARD)
    items, _ = build("salt", 5, rotation="frozen", center=7)
    for fam in HARD:
        assert sorted(i.level for i in items if i.family == fam) == [5, 6, 7, 8, 9]
    again, _ = build("salt", 5, rotation="frozen", center=7)
    assert [i.prompt for i in items] == [i.prompt for i in again]
    other_week, _ = build("salt", 5, rotation="weekly", when=__import__("datetime").date(2026, 1, 5), center=7)
    assert {i.prompt for i in items if i.family == "trace"}.isdisjoint(i.prompt for i in other_week if i.family == "trace")


def test_baseline_restarts_when_the_family_mix_changes():
    old, new = frozenset(ORDER[:7]), frozenset(ORDER)
    runs = [{"id": i} for i in range(1, 9)]
    fams = {1: old, 2: old, 3: old, 4: new, 5: new, 6: frozenset(), 7: new}  # 6: no results, 8: missing
    assert [r["id"] for r in current_suite(runs, fams)] == [4, 5, 6, 7, 8]
    assert current_suite(runs, {i: new for i in range(1, 9)}) == runs
    assert current_suite([], {}) == []


def test_analyze_drops_runs_from_an_older_family_mix(tmp_path, monkeypatch):
    monkeypatch.setenv("NERFWATCH_HOME", str(tmp_path))
    from nerfwatch import db
    from nerfwatch.analyze import analyze

    target = {"name": "t", "backend": "openai-compatible"}
    with db.connect() as con:
        for fams in [ORDER[:7]] * 6 + [ORDER] * 3:
            rid = db.new_run(con, target, "h", len(fams), False)
            for f in fams:
                db.add_result(con, rid, {"item_hash": f, "family": f, "level": 5, "difficulty": 2.0, "score": 1.0, "latency_ms": 100.0,
                                         "ttft_ms": None, "output_tokens": 5, "reasoning_tokens": None, "output_chars": 5,
                                         "refused": 0, "lazy": 0, "error": None, "response": "x"})
    ta = analyze("t", {})
    assert len(ta.runs) == 3 and ta.verdict.startswith("building baseline (3/5")
