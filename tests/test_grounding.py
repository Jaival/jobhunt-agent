"""Grounding check in build_application.py: numbers and skill terms in letters must come from the candidate's files."""
import pytest

from test_sample_de import APP as APP_DE
from test_sample_workspace import APP


def edit(root, app, old, new):
    path = root / app / "application.md"
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def test_sample_passes_with_ad_only_warning(tool):
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 0, r.stderr
    assert "from the ad only, not in your files: SEO" in r.stdout


def test_invented_metric_fails(tool, sample):
    edit(sample, APP, "the account gained 1,200 new followers", "website traffic increased by 40%")
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 1
    assert "letter: not in your CV, CLAUDE.md, projects.md or the ad: 40%" in r.stderr


def test_thousands_separator_matches_any_form(tool, sample):
    edit(sample, APP, "1,200 new followers", "1.200 new followers")
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 0, r.stderr


def test_gap_from_claude_md_is_not_a_source(tool, sample):
    # HubSpot is only under "Gaps (never claim these)" in CLAUDE.md, and not in the ad.
    edit(sample, APP, "in Google Sheets", "in HubSpot")
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 1 and "the ad: HubSpot" in r.stderr


def test_grounding_ok_lets_a_reviewed_term_through(tool, sample):
    edit(sample, APP, "in Google Sheets", "in HubSpot")
    edit(sample, APP, "short: Example-Company", "short: Example-Company\ngrounding_ok: [HubSpot]")
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 0, r.stderr


def test_without_ad_json_ad_terms_fail(tool, sample):
    (sample / APP / "ad.json").unlink()
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 1 and "the ad: SEO" in r.stderr


def test_headline_is_checked(tool, sample):
    edit(sample, APP, "Instagram, LinkedIn & Analytics", "Instagram, Salesforce & Analytics")
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 1 and "CV headline: not in your CV, CLAUDE.md, projects.md or the ad: Salesforce" in r.stderr


def test_exact_case_terms_ignore_ordinary_words(tool, sample):
    edit(sample, APP, "kept what worked", "cut the slack and kept what worked")
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 0, r.stderr


def test_german_sample_passes(tool_de):
    r = tool_de("build_application.py", APP_DE, "--no-pdf")
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("old, new, missing", [
    ("die Masse um 18 Prozent gesenkt", "die Masse um 25 Prozent gesenkt", "letter DE: "),
    ("in CATIA V5 konstruiert", "in SolidWorks und Siemens NX konstruiert", "Siemens NX"),
])
def test_german_letter_claims_fail(tool_de, sample_de, old, new, missing):
    edit(sample_de, APP_DE, old, new)
    r = tool_de("build_application.py", APP_DE, "--no-pdf")
    assert r.returncode == 1 and missing in r.stderr
    assert "letter EN" not in r.stderr                       # only the edited language is reported


def test_numbers_normalise(monkeypatch):
    import sys
    from conftest import SAMPLE
    monkeypatch.setenv("JOBHUNT_ROOT", str(SAMPLE))       # config.py reads it on import
    for name in ("config", "build_application"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    import build_application as b
    assert b.numbers("1,200 and 1.200, 2,5 or 2.5, 031, 18 % and 18 Prozent") == {"1200", "2.5", "31", "18%"}
    assert b.numbers("CATIA V5, GA4 and B2") == set()
