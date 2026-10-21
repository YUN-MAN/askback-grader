from pathlib import Path

from grader import aggregate, llm, rules

V = Path("data/good/V11.mp4")


def test_parse_json_fenced():
    assert llm.parse_json('前言 ```json\n{"a": 1}\n``` 後記') == {"a": 1}


def test_parse_json_strips_think():
    assert llm.parse_json('<think>x{</think>{"a": 2}') == {"a": 2}


def test_rules_good_video():
    from grader import perceive
    r = rules.check(perceive.probe(V), V)
    assert r["hard_fail"] == [] and r["score"] > 80


def test_hard_fail_caps_total():
    rl = {"score": 100, "hard_fail": ["duration"], "unverified": [], "checks": []}
    ok = {"score": 100, "reason": "x"}
    rev = {"correctness": ok, "responsiveness": ok, "grade_fit": ok, "continuity": ok, "errors": []}
    out = aggregate.aggregate(rl, {"gain_score": 100, "n_valid": 3, "fixed": 100}, rev, mock=True)
    assert out["score"] <= aggregate.HARD_FAIL_CAP
