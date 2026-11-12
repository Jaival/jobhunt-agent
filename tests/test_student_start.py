"""Student letters must state the start: a fixed phrase ("as soon as possible") or a concrete date."""
import sys

import pytest

from conftest import SAMPLE
from test_grounding import edit
from test_sample_workspace import APP

START = "I could start as soon as possible"


@pytest.fixture
def b(monkeypatch):
    monkeypatch.setenv("JOBHUNT_ROOT", str(SAMPLE))       # config.py reads it on import
    for name in ("config", "build_application"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    import build_application
    return build_application


@pytest.mark.parametrize("text", [
    "i can start on 1 march 2027.", "available from march 2027", "i can start on the 15th of april 2027",
    "ich kann ab dem 1. märz 2027 beginnen", "ab märz 2027 verfügbar", "start: 01.03.2027", "beginn am 1.3.2027",
    "from 1 may", "ab 1. mai",
])
def test_a_date_counts_as_the_start(b, text):
    assert b.START_DATE.search(text)


@pytest.mark.parametrize("text", [
    "i may join your team", "i worked there for 12 months", "in the summer semester", "version 1.3.2 of the tool",
    "mai tai", "we march forward",
])
def test_other_text_is_not_a_start_date(b, text):
    assert not b.START_DATE.search(text)


def test_a_letter_with_a_start_date_builds(tool, sample):
    claude = sample / "CLAUDE.md"                            # the candidate's own start date (grounds 1 and 2027)
    text = claude.read_text(encoding="utf-8")
    assert "Rule 9 values: start as soon as possible" in text
    claude.write_text(text.replace("Rule 9 values: start as soon as possible", "Rule 9 values: start 1 March 2027"),
                      encoding="utf-8")
    edit(sample, APP, START, "I could start from 1 March 2027")
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 0, r.stderr


def test_a_letter_without_a_start_fails(tool, sample):
    edit(sample, APP, START, "I could start soon")
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode != 0
    assert "must state the start" in r.stderr
