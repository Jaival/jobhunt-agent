"""Version stamping (S4-3): the brief, job.md and every ledger write say which engine (and model) made them;
the documents an employer gets don't."""
import json
import sys

import docx

import permissions
from test_sample_workspace import APP

ENGINE = permissions.TEMPLATE.parents[3]


def test_record_stamps_engine_and_model(ledger_mod, monkeypatch, tmp_path):
    cands = tmp_path / "candidates.json"
    cands.write_text(json.dumps({"jobs": [dict(id="an-1", source="Arbeitnow", company="Acme", posted="2026-10-27",
                                               title="Werkstudent Marketing", url="https://example.org/1")]}),
                     encoding="utf-8")
    monkeypatch.setattr(ledger_mod, "CANDIDATES", cands)
    monkeypatch.setattr(ledger_mod.version, "version", lambda: "1.0.0")
    monkeypatch.setattr(sys, "argv", ["ledger.py", "record", "--model", "claude-opus-5-5"])
    assert ledger_mod.main() == 0
    row = ledger_mod.load()[0]
    assert row["engine_version"] == "1.0.0" and row["model"] == "claude-opus-5-5"


def test_routine_and_tailor_ask_for_the_stamps():
    routine = (ENGINE / "ROUTINE.md").read_text(encoding="utf-8")
    assert "`engine 0.3.0 (a1b2c3d) · model <your model id>`" in routine        # brief header
    assert "ledger.py record --model <your model id>" in routine
    assert routine.count("--model <your model id>") >= 3                         # record, set (step 4), set tailored
    tailor = (permissions.TEMPLATE.parent / "agents" / "tailor.md").read_text(encoding="utf-8")
    assert "- **Engine:** <the output of\n   python engine/tools/version.py> · model <your model id>" in tailor


def test_documents_carry_no_engine_version(tool, sample):
    """ATS and recruiters see only the applicant: no engine name or version in the docx metadata."""
    assert tool("build_application.py", APP, "--no-pdf").returncode == 0
    built = list((sample / APP).glob("*.docx"))
    assert len(built) >= 2                                                       # CV and letter
    for f in built:
        cp = docx.Document(str(f)).core_properties
        meta = " ".join(str(getattr(cp, k) or "") for k in ("author", "title", "subject", "keywords", "comments",
                                                           "category", "last_modified_by"))
        assert "engine" not in meta.lower() and "jobhunt" not in meta.lower(), meta
        assert cp.author == "Lena Fischer"
