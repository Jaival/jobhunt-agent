"""Ledger expiry: a screened, skipped or closed job counts as new again after ledger_expiry_days (S2-6)."""
import datetime as dt
import json
import sys

import pytest

OLD = f"{dt.date.today() - dt.timedelta(days=91):%Y-%m-%d}"
RECENT = f"{dt.date.today() - dt.timedelta(days=89):%Y-%m-%d}"


def index(ledger, verdict, first_seen):
    idx = ledger.Index([])
    idx.add(company="Acme GmbH", title="Werkstudent Marketing", url="https://example.org/1", job_id="ba-1",
            verdict=verdict, score="61", first_seen=first_seen)
    return idx


def run(ledger, monkeypatch, capsys, *args):
    monkeypatch.setattr(sys, "argv", ["ledger.py", *args])
    assert ledger.main() == 0
    return capsys.readouterr().out


@pytest.mark.parametrize("verdict", ["screened", "skipped", "closed"])
def test_old_screened_jobs_expire(ledger_mod, verdict):
    assert index(ledger_mod, verdict, OLD).find("Acme", "Werkstudent Marketing") is None
    assert index(ledger_mod, verdict, RECENT).find("Acme", "Werkstudent Marketing")


@pytest.mark.parametrize("verdict", ["tailored", "applied", "rejected", "interview"])
def test_jobs_acted_on_never_expire(ledger_mod, verdict):
    assert index(ledger_mod, verdict, "2020-01-01").find(url="https://example.org/1")


def test_blank_date_stays_seen(ledger_mod):
    assert index(ledger_mod, "screened", "").find(job_id="ba-1")


def test_zero_days_never_expires(ledger_mod, monkeypatch):
    monkeypatch.setattr(ledger_mod, "EXPIRY_DAYS", 0)
    assert index(ledger_mod, "skipped", "2020-01-01").find("Acme", "Werkstudent Marketing")


def test_check_says_expired(ledger_mod, monkeypatch, capsys):
    ledger_mod.save(index(ledger_mod, "skipped", OLD).rows)
    out = run(ledger_mod, monkeypatch, capsys, "check", "Acme", "Werkstudent Marketing (m/w/d)")
    assert out.startswith(f"NEW (seen {OLD} skipped 61, expired)")


def test_record_reuses_the_expired_row(ledger_mod, monkeypatch, capsys, tmp_path):
    ledger_mod.save(index(ledger_mod, "skipped", OLD).rows)
    cands = tmp_path / "candidates.json"
    cands.write_text(json.dumps({"jobs": [dict(id="ba-2", source="Arbeitsagentur", company="Acme",
                                               title="Werkstudent Marketing", url="https://example.org/2",
                                               posted="2026-10-27")]}), encoding="utf-8")
    monkeypatch.setattr(ledger_mod, "CANDIDATES", cands)
    assert "recorded 1 new jobs, 1 in ledger" in run(ledger_mod, monkeypatch, capsys, "record")
    [row] = ledger_mod.load()
    assert row["first_seen"] == f"{dt.date.today():%Y-%m-%d}" and row["verdict"] == "screened"
    assert row["url"] == "https://example.org/2" and row["score"] == ""
    assert row["note"] == f"posted 2026-10-27; seen {OLD} skipped 61"
