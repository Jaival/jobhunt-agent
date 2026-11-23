"""keywords.py: the ad's key terms against the CV, the letter and the candidate's files; skills.md answers."""
import datetime as dt
import json
import shutil
import sys

import pytest

from conftest import SAMPLE
from test_grounding import edit
from test_sample_workspace import APP

TERMS = [("Instagram", "critical"), ("SEO", "preferred"), ("Mailchimp", "high"), ("Agile", "high"),
         ("Python", "meaningful"), ("Google Analytics", "high"), ("HubSpot", "preferred"),
         ("small local brands", "meaningful")]


@pytest.fixture
def kw(monkeypatch):
    """tools/keywords.py imported against the sample workspace (config.py reads JOBHUNT_ROOT at import)."""
    monkeypatch.setenv("JOBHUNT_ROOT", str(SAMPLE))
    for name in ("config", "keywords"):
        sys.modules.pop(name, None)
    import keywords
    yield keywords
    for name in ("config", "keywords"):
        sys.modules.pop(name, None)


def set_keywords(folder, terms=TERMS):
    ad = json.loads((folder / "ad.json").read_text(encoding="utf-8"))
    ad["keywords"] = [{"term": t, "importance": i, "where": "requirements"} for t, i in terms]
    (folder / "ad.json").write_text(json.dumps(ad), encoding="utf-8")


def statuses(tool, folder=APP):
    r = tool("keywords.py", "check", folder, "--json")
    assert r.returncode == 0, r.stderr
    result = json.loads(r.stdout)
    return {t["term"]: t["status"] for t in result["terms"]}, result


@pytest.mark.parametrize("term, text, hit", [
    ("C++", "Kenntnisse in C++ und Python", True),
    ("CI/CD", "built CI/CD pipelines", True),
    ("Java", "JavaScript and TypeScript", False),
    ("Java", "Java-Kenntnisse", True),
    ("Machine Learning", "machine-learning models", True),
    (".NET", "C# and .NET services", True),
    ("Node.js", "NodeJS", False),
])
def test_pattern_matches_whole_terms(kw, term, text, hit):
    assert bool(kw.pattern(term).search(text)) is hit


def test_aliases_match_both_ways(kw):
    groups = kw.alias_groups([{"skill": "Agile", "aliases": ["Scrum"], "status": "yes", "note": "x"}])
    assert kw.found("Kubernetes", "deployed on k8s", groups)
    assert kw.found("k8s", "Kubernetes clusters", groups)
    assert kw.found("Datenbanken", "SQL databases", groups)
    assert kw.found("Agile", "two-week Scrum sprints", groups)
    assert not kw.found("Agile", "fast-moving team", groups)


def test_check_splits_the_terms_by_status(sample, tool):
    set_keywords(sample / APP)
    found, result = statuses(tool)
    assert found == {"Instagram": "cv", "Google Analytics": "cv", "small local brands": "letter",
                     "Mailchimp": "addable", "SEO": "no", "HubSpot": "no", "Agile": "confirm", "Python": "confirm"}
    # weights: cv = 3 + 2 of 3+0.5+2+2+1+2+0.5+1 = 12
    assert result["match"] == 42 and result["top"] == [2, 4] and result["cv_source"] == "master CV"
    out = tool("keywords.py", "check", APP).stdout
    assert "| Instagram | critical | requirements | cv |" in out
    assert out.strip().endswith("ATS match 42%, critical/high in CV 2/4; confirm: Agile, Python")


def test_answers_in_skills_md_change_the_status(sample, tool):
    set_keywords(sample / APP)
    assert tool("keywords.py", "fact", "Agile", "yes", "--note", "Scrum sprints at Example Media",
                "--alias", "Scrum").returncode == 0
    assert tool("keywords.py", "fact", "Python", "learning").returncode == 0
    assert tool("keywords.py", "fact", "Mailchimp", "no").returncode == 0
    found, _ = statuses(tool)
    assert found["Agile"] == "addable" and found["Python"] == "learning" and found["Mailchimp"] == "no"


def test_the_built_cv_is_used_once_it_exists(sample, tool):
    set_keywords(sample / APP)
    assert tool("build_application.py", APP, "--no-pdf").returncode == 0
    _, result = statuses(tool)
    assert result["cv_source"] == "built CV"


def test_old_extract_without_keywords(tool):
    r = tool("keywords.py", "check", APP)
    assert r.returncode == 0 and r.stdout.startswith("no keywords in this extract")


def test_fact_needs_a_note_for_yes_and_updates_in_place(sample, tool):
    r = tool("keywords.py", "fact", "Agile", "yes")
    assert r.returncode == 1 and "needs --note" in r.stderr
    assert not (sample / "skills.md").exists()
    assert tool("keywords.py", "fact", "Agile", "learning", "--alias", "Scrum").returncode == 0
    assert tool("keywords.py", "fact", "agile", "yes", "--note", "Example Media sprints").returncode == 0
    text = (sample / "skills.md").read_text(encoding="utf-8")
    assert text.count("| Agile") + text.count("| agile") == 1
    assert "| agile | yes | Example Media sprints | Scrum |" in text   # the aliases stay
    assert tool("keywords.py", "fact", "A|B", "no").returncode == 1


def test_grounding_accepts_a_yes_skill_and_refuses_a_learning_one(sample, tool):
    edit(sample, APP, "in Google Sheets", "in Google Sheets and planned the work in Scrum sprints")
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 1 and "skills.md or the ad: Scrum" in r.stderr
    tool("keywords.py", "fact", "Scrum", "learning")
    assert tool("build_application.py", APP, "--no-pdf").returncode == 1
    tool("keywords.py", "fact", "Scrum", "yes", "--note", "two-week sprints in the Example Media team")
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 0, r.stderr


def test_ask_lists_unknown_terms_of_recent_drafts(sample, tool):
    old = sample / APP
    today = dt.date.today().isoformat()
    recent = old.parent / f"{today}_Other-Company_Working-Student"
    shutil.copytree(old, recent)
    set_keywords(recent)
    ad = json.loads((recent / "ad.json").read_text(encoding="utf-8"))
    (recent / "ad.json").write_text(json.dumps({**ad, "company": "Other GmbH"}), encoding="utf-8")
    set_keywords(old)   # dated 2026-10-23: too old to ask about
    r = tool("keywords.py", "ask", "--days", "14")
    assert r.returncode == 0
    assert r.stdout.splitlines() == ["ASK     Agile | asked by Other GmbH", "ASK     Python | asked by Other GmbH",
                                     "2 skill question(s)"]
