"""Ledger sub-scores and versions (S2-4): optional columns, ledger_version in the meta file, `set --subscores`."""
import csv
import json
import sys

OLD_HEADER = "key,job_id,source,company,title,url,first_seen,verdict,score,note\n"
OLD_ROW = "acme|werkstudent marketing,ba-1,ba,Acme GmbH,Werkstudent Marketing,https://example.org/1,2026-10-20,screened,,\n"


def write_old(ledger):
    ledger.LEDGER.parent.mkdir(parents=True, exist_ok=True)
    ledger.LEDGER.write_text(OLD_HEADER + OLD_ROW, encoding="utf-8")


def run(ledger, monkeypatch, capsys, *args):
    monkeypatch.setattr(sys, "argv", ["ledger.py", *args])
    code = ledger.main()
    out = capsys.readouterr()
    return code, out.out + out.err


def test_old_ledger_loads_with_blank_columns(ledger_mod):
    write_old(ledger_mod)
    row = ledger_mod.load()[0]
    assert row["subscores"] == row["engine_version"] == row["model"] == "" and row["company"] == "Acme GmbH"


def test_set_subscores_writes_columns_and_meta(ledger_mod, monkeypatch, capsys):
    write_old(ledger_mod)
    monkeypatch.setattr(ledger_mod.version, "version", lambda: "0.5.0-dev")
    code, _ = run(ledger_mod, monkeypatch, capsys, "set", "ba-1", "--verdict", "tailored", "--score", "81",
                  "--subscores", "hours=4", "skills=4", "seniority=5", "language=3", "location=5",
                  "--model", "claude-opus-5-5")
    assert code == 0
    with ledger_mod.LEDGER.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["subscores"] == "skills=4 seniority=5 language=3 location=5 hours=4"   # rubric order
    assert rows[0]["engine_version"] == "0.5.0-dev" and rows[0]["model"] == "claude-opus-5-5"
    assert rows[0]["score"] == "81" and rows[0]["verdict"] == "tailored"
    assert json.loads(ledger_mod.META.read_text(encoding="utf-8")) == {"ledger_version": 2}


def test_set_refuses_incomplete_or_out_of_range_subscores(ledger_mod, monkeypatch, capsys):
    write_old(ledger_mod)
    code, out = run(ledger_mod, monkeypatch, capsys, "set", "ba-1", "--verdict", "screened",
                    "--subscores", "skills=4", "skills=5", "language=3", "location=5", "hours=4")
    assert code == 1 and "each of skills" in out
    code, out = run(ledger_mod, monkeypatch, capsys, "set", "ba-1", "--verdict", "screened",
                    "--subscores", "skills=9", "seniority=5", "language=3", "location=5", "hours=4")
    assert code == 1
    assert ledger_mod.load()[0]["subscores"] == ""
