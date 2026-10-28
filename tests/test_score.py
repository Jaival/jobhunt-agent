"""Rubric scoring (S2-3): fixed sub-scores give a fixed total; weights, bonus and hard mismatches from config."""
import json

import pytest

import score
from test_extract import GOOD

ST = score.settings({"profile": {"score_bonus": ["Instagram", "Canva", "Google Analytics"]}})
ALL5 = dict.fromkeys(score.CRITERIA, 5)


def sub(**kw):
    return {**ALL5, **kw}


@pytest.mark.parametrize("subscores, total", [
    (ALL5, 95),
    (sub(skills=4, location=4, hours=3), 81),             # 88 - 2 - 5
    (sub(skills=3, seniority=3), 65),                     # 70 - 5
    (sub(skills=2, seniority=2, language=4, location=4, hours=2), 38),  # 58 - 8 - 2 - 2 - 8
    (dict.fromkeys(score.CRITERIA, 1), 0),                # 35 - 4 * 20, not below 0
])
def test_total(subscores, total):
    assert score.compute(subscores, ST)["score"] == total


def test_same_subscores_same_total():
    s = sub(skills=3, language=2)
    assert len({score.compute(s, ST, "Canva")["score"] for _ in range(5)}) == 1


def test_bonus_for_named_skills_at_most_two():
    s = sub(skills=3, seniority=3)
    r = score.compute(s, ST, "Instagram, Canva und Google Analytics")
    assert r["score"] == 71 and r["bonus"] == ["Instagram", "Canva"] and "bonus +6 for Instagram, Canva" in r["reasons"]
    assert score.compute(s, ST, "Canvas-Druck")["bonus"] == []  # whole words only
    assert score.compute(ALL5, ST, "Canva Instagram")["score"] == 100


@pytest.mark.parametrize("criterion", score.BLOCKERS)
def test_zero_on_a_blocker_is_a_hard_mismatch(criterion):
    r = score.compute(sub(**{criterion: 0}), ST, "Canva Instagram")
    assert r["hard_mismatch"] == [criterion] and r["score"] == 36  # (95 - 30 + 6) / 2
    assert f"halved: hard mismatch ({criterion})" in r["reasons"]


def test_a_hard_mismatch_is_always_below_60():
    assert score.compute(sub(location=0), ST, "Canva Instagram")["score"] < 60


def test_zero_skills_is_not_a_hard_mismatch():
    r = score.compute(sub(skills=0), ST)
    assert r["hard_mismatch"] == [] and r["score"] == 15


def test_reasons_show_each_step():
    assert score.compute(sub(skills=4, language=3), ST)["reasons"] == [
        "skills 4/5: base 88", "seniority 5/5", "language 3/5: -5", "location 5/5", "hours 5/5"]


def test_config_overrides():
    st = score.settings({"scoring": {"weights": {"hours": 0, "location": 2}, "blockers": ["location"],
                                     "bonus_points": 0}, "profile": {"score_bonus": ["Canva"]}})
    r = score.compute(sub(hours=0, location=3), st, "Canva")
    assert r["hard_mismatch"] == [] and r["score"] == 85 and r["bonus"] == ["Canva"]   # 95 - 2 * 5, no bonus points
    assert score.compute(sub(location=0), st)["hard_mismatch"] == ["location"]


@pytest.mark.parametrize("cfg", [
    {"scoring": {"weight": {}}}, {"scoring": {"weights": {"salary": 1}}}, {"scoring": {"weights": {"skills": 2}}},
    {"scoring": {"weights": {"hours": -1}}}, {"scoring": {"blockers": ["skils"]}},
    {"scoring": {"bonus_points": "3"}}, {"scoring": [1]},
])
def test_bad_config_is_refused(cfg):
    with pytest.raises(ValueError, match="config.yaml scoring"):
        score.settings(cfg)


@pytest.mark.parametrize("bad", [sub(skills=6), sub(skills=2.5), {"skills": 3}, sub(salary=3)])
def test_bad_subscores_are_refused(bad):
    with pytest.raises(ValueError, match="sub-scores"):
        score.compute(bad, ST)


def test_ad_text_reads_title_requirements_and_tasks():
    text = score.ad_text(GOOD)
    assert "Werkstudent:in Marketing" in text and "idealerweise Canva" in text and "KPI-Reporting" in text


def test_cli(tool, sample):
    ad = sample / "data" / "ads" / "ba-1.json"
    ad.parent.mkdir(parents=True)
    ad.write_text(json.dumps(GOOD), encoding="utf-8")
    r = tool("score.py", "skills=4", "seniority=5", "language=3", "location=5", "hours=4", "--ad", ad, "--json")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["score"] == 84 and json.loads(r.stdout)["bonus"] == ["Canva"]   # 88 - 5 - 2 + 3
    r = tool("score.py", "skills=4", "seniority=5", "language=3", "location=0", "hours=4")
    assert r.returncode == 0 and r.stdout.startswith("score 26  hard mismatch: location")
    r = tool("score.py", "skills=4", "seniority=five")
    assert r.returncode == 1 and "write criterion=N" in r.stderr
