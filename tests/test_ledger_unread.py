"""Jobs the reader couldn't read stay out of the ledger so the next run tries again; a gone page counts as closed."""
import json
import sys


def test_record_leaves_unread_jobs_out_and_closes_gone_pages(ledger_mod, monkeypatch, capsys, tmp_path):
    job = dict(source="Arbeitnow", company="Acme", posted="2026-10-27")
    cands = tmp_path / "candidates.json"
    cands.write_text(json.dumps({"jobs": [
        dict(job, id="an-1", title="Werkstudent Marketing", url="https://example.org/1"),
        dict(job, id="an-2", title="Werkstudent Vertrieb", url="https://example.org/2", read_error="blocked"),
        dict(job, id="an-3", title="Werkstudent IT", url="https://example.org/3", read_error="gone")]}),
        encoding="utf-8")
    monkeypatch.setattr(ledger_mod, "CANDIDATES", cands)
    monkeypatch.setattr(sys, "argv", ["ledger.py", "record"])
    assert ledger_mod.main() == 0
    assert "recorded 2 new jobs, 2 in ledger; 1 unread job(s) left out" in capsys.readouterr().out
    assert {r["job_id"]: r["verdict"] for r in ledger_mod.load()} == {"an-1": "screened", "an-3": "closed"}
