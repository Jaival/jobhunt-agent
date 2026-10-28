"""The eval harness (S2-5) offline: prompt, grading, the baseline files and the comparison. No model calls."""
import json

import pytest

import eval_run
from test_extract import GOOD

EXP_GOOD = {"in_scope": True, "role_type": "Werkstudent", "hard_mismatch": None, "score": [75, 92],
            "german_required": "C1+"}
EXP_FAR = {"in_scope": True, "role_type": "Werkstudent", "hard_mismatch": "location: Berlin", "score": [0, 45],
           "german_required": "B2"}
EXP_OUT = {"in_scope": False, "role_type": "Other", "hard_mismatch": None, "score": None, "german_required": "unknown"}


def judgment(**kw):
    return {"in_scope": True, "role_type": "Werkstudent", "hard_mismatch": None, "score": 80,
            "german_required": "C1+", "reasons": "", **kw}


def test_system_prompt_has_the_routine_and_the_candidate():
    text = eval_run.system_prompt()
    assert "4. Score each remaining job 0-100" in text and "5. Tailor" not in text
    assert "Lena Fischer" in text and "Rules for every application" in text and "# Fit-score rubric" in text


def test_scored_runs_score_py_on_the_subscores():
    sub = dict.fromkeys(eval_run.score.CRITERIA, 5)
    got = eval_run.scored({"in_scope": True, "subscores": {**sub, "skills": 3}}, "Canva und Instagram")
    assert got["score"] == 76 and got["hard_mismatch"] is None   # 70 + 2 bonus skills
    got = eval_run.scored({"in_scope": True, "subscores": {**sub, "location": 0}}, "")
    assert got["score"] == 32 and got["hard_mismatch"] == "location"
    assert eval_run.scored({"in_scope": False, "subscores": None}, "")["score"] is None


def test_user_prompt_is_the_extract():
    ad = eval_run.load_ad(sorted(eval_run.ADS.glob("*.md"))[0])
    text = eval_run.user_prompt(ad, {**GOOD, "id": ad["id"]})
    assert f"data/ads/{ad['id']}.json" in text and '"german_required": "C1+"' in text and ad["text"][:50] not in text


def test_grade_agreement():
    assert eval_run.grade(EXP_GOOD, judgment()) == {
        "in_scope": True, "german": True, "role_type": True, "hard_mismatch": True, "score": True, "tailor": True}


def test_grade_disagreements():
    g = eval_run.grade(EXP_GOOD, judgment(score=65, german_required="B2", role_type="Internship"))
    assert g == {"in_scope": True, "german": False, "role_type": False, "hard_mismatch": True, "score": False,
                 "tailor": False}


def test_hard_mismatch_means_no_tailoring():
    g = eval_run.grade(EXP_FAR, judgment(score=82, german_required="B2"))
    assert g["hard_mismatch"] is False and g["tailor"] is False and g["score"] is False
    assert eval_run.grade(EXP_FAR, judgment(score=30, hard_mismatch="location", german_required="B2"))["tailor"]


def test_out_of_scope_ads_count_scope_and_german_only():
    g = eval_run.grade(EXP_OUT, judgment(in_scope=False, role_type="Other", score=None, german_required="unknown"))
    assert g == {"in_scope": True, "german": True, "tailor": True}


def test_borderline_range_is_not_a_tailor_case():
    exp = {**EXP_GOOD, "score": [62, 80]}
    assert "tailor" not in eval_run.grade(exp, judgment())


def run_of(results, version="0.3.0"):
    return {"version": version, "engine": version, "model": "m", "date": "2026-11-09", "cost_usd": 0.5,
            "results": results, "summary": eval_run.summarise(results)}


def result(exp, got, ad="01-x"):
    return {"ad": ad, "expected": exp, "got": got, "grades": eval_run.grade(exp, got)}


def test_render_marks_disagreements():
    run = run_of([result(EXP_GOOD, judgment()), result(EXP_FAR, judgment(score=82), "02-far"),
                  {"ad": "03-err", "expected": EXP_OUT, "error": "timeout", "got": {}, "grades": {}}])
    md = eval_run.render(run)
    assert "| In scope | 2/2 (100%) |" in md and "| Hard mismatch yes/no (in-scope ads) | 1/2 (50%) |" in md
    assert "**- / -**" not in md and "**location: Berlin / -**" in md and "**[0, 45] / 82**" in md
    assert "| 03-err | error: timeout |" in md


def test_compare_flags_a_drop_beyond_tolerance():
    good = [result(EXP_GOOD, judgment(), f"{i:02}") for i in range(5)]
    worse = good[:2] + [result(EXP_GOOD, judgment(score=50), f"{i:02}") for i in range(2, 5)]
    lines, regressed = eval_run.compare(run_of(good), run_of(worse, "0.4.0"), tolerance=2)
    assert regressed and "Score inside the range: 5/5 -> 2/5 REGRESSION" in lines
    assert not eval_run.compare(run_of(good), run_of(worse, "0.4.0"), tolerance=3)[1]


def test_run_writes_both_files(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(eval_run, "BASELINES", tmp_path)
    answer = {**judgment(), "subscores": dict.fromkeys(eval_run.score.CRITERIA, 5)}
    monkeypatch.setattr(eval_run, "ask", lambda system, user, model: (answer, "claude-test", 0.01))
    monkeypatch.setattr(eval_run.extract, "read_text", lambda job, text, model: (dict(GOOD), "claude-test", 0.02))
    args = eval_run.argparse.Namespace(only="01,02", model=None, label="9.9.9", jobs=2)
    assert eval_run.cmd_run(args) == 0
    data = json.loads((tmp_path / "v9.9.9.json").read_text(encoding="utf-8"))
    assert [r["ad"][:2] for r in data["results"]] == ["01", "02"] and data["model"] == "claude-test"
    assert data["results"][1]["extract"]["id"].startswith("ba-") and data["results"][1]["extract"]["id"] != GOOD["id"]
    assert data["cost_usd"] == pytest.approx(0.06)
    assert (tmp_path / "v9.9.9.md").read_text(encoding="utf-8").startswith("# Eval baseline v9.9.9")


@pytest.mark.parametrize("path", sorted(eval_run.BASELINES.glob("*.json")), ids=lambda p: p.stem)
def test_checked_in_baselines_cover_every_ad(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    assert {r["ad"] for r in data["results"]} == {p.stem for p in eval_run.ADS.glob("*.md")}
    assert data["summary"] == eval_run.summarise(data["results"])
