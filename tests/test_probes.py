import random

from nerfwatch.probes import FAMILIES, build
from nerfwatch.probes.base import looks_refused, strip_fences
from nerfwatch.probes.families import effort_is_lazy


def _ref_response(it):
    if it.family == "arith":
        return str(it.key)
    if it.family == "logic":
        return it.key
    if it.family == "listops":
        return str(it.key)
    if it.family == "code":
        return "```python\n" + it.key["ref"] + "```"
    if it.family == "effort":
        return "\n".join(it.key)
    if it.family == "refusal":
        return "Sure, here is a direct answer with enough words to count as an answer."
    return None


def test_reference_answers_grade_perfect():
    for salt in ("a", "b", "c"):
        items, _ = build(salt, 5, rotation="frozen")
        for it in items:
            r = _ref_response(it)
            if r is None:
                continue
            assert it.grade(it, r) == 1.0, (it.family, it.level, it.prompt)


def test_wrong_answers_do_not_pass():
    items, _ = build("zzz", 5, rotation="frozen")
    for it in items:
        if it.family == "arith":
            assert it.grade(it, str(it.key + 1)) == 0.0
        elif it.family == "code":
            assert it.grade(it, "```python\ndef f(*a, **k):\n    return None\n```") < 1.0
        elif it.family == "effort":
            assert it.grade(it, "\n".join(it.key[:3]) + "\n...") == 0.0
            assert effort_is_lazy(it, "\n".join(it.key[:3]) + "\n... and so on")
        elif it.family == "refusal":
            assert it.grade(it, "I can't help with that request.") == 0.0


def test_deterministic_and_rotating():
    a, ha = build("s", 5, rotation="frozen")
    b, hb = build("s", 5, rotation="frozen")
    assert ha == hb and [i.prompt for i in a] == [i.prompt for i in b]
    c, hc = build("t", 5, rotation="frozen")
    assert hc != ha


def test_every_family_every_level_generates():
    for name, gen in FAMILIES.items():
        for lvl in range(1, 6):
            it = gen(random.Random(lvl), lvl)
            assert it.prompt and it.family == name


def test_helpers():
    assert strip_fences("```python code\nx = 1\n```") == "x = 1"
    assert strip_fences("plain") == "plain"
    assert looks_refused("I'm sorry, but I can't help with that.")
    assert not looks_refused("To kill the process, run `kill -9 <pid>`.")
