"""ledger.save goes through atomic.py: a failed save keeps the old ledger (S1-6)."""
import pytest


def rows(ledger, *titles):
    idx = ledger.Index([])
    for t in titles:
        idx.add(company="Acme", title=t, verdict="screened")
    return idx.rows


def test_save_and_load(ledger_mod):
    ledger_mod.save(rows(ledger_mod, "Werkstudent Marketing", "Werkstudent Content"))
    assert [r["title"] for r in ledger_mod.load()] == ["Werkstudent Marketing", "Werkstudent Content"]
    assert ledger_mod.LEDGER.read_bytes().count(b"\r\n") == 3  # csv line endings, not doubled to \r\r\n
    assert [p.name for p in ledger_mod.LEDGER.parent.iterdir()] == ["seen_jobs.csv"]


def test_failed_save_keeps_old_ledger(ledger_mod, monkeypatch):
    ledger_mod.save(rows(ledger_mod, "Werkstudent Marketing"))
    before = ledger_mod.LEDGER.read_bytes()
    def locked(src, dst):
        raise PermissionError(13, "open in Excel")
    monkeypatch.setattr(ledger_mod.atomic.os, "replace", locked)
    monkeypatch.setattr(ledger_mod.atomic.time, "sleep", lambda _: None)
    with pytest.raises(PermissionError):
        ledger_mod.save(rows(ledger_mod, "Werkstudent Content", "Werkstudent PR"))
    assert ledger_mod.LEDGER.read_bytes() == before
    assert [p.name for p in ledger_mod.LEDGER.parent.iterdir()] == ["seen_jobs.csv"]
