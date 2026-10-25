"""Ledger save is atomic: a crash while writing keeps the old ledger and leaves no temp file (S1-6)."""
import os

import pytest

from conftest import SAMPLE

os.environ["JOBHUNT_ROOT"], _old = str(SAMPLE), os.environ.get("JOBHUNT_ROOT")
import ledger  # noqa: E402  (config.py reads JOBHUNT_ROOT on import)
if _old is None:
    del os.environ["JOBHUNT_ROOT"]
else:
    os.environ["JOBHUNT_ROOT"] = _old


@pytest.fixture
def csv_path(tmp_path, monkeypatch):
    p = tmp_path / "data" / "seen_jobs.csv"
    monkeypatch.setattr(ledger, "LEDGER", p)
    return p


def rows(*titles):
    idx = ledger.Index([])
    for t in titles:
        idx.add(company="Acme", title=t, verdict="screened")
    return idx.rows


def test_save_and_load(csv_path):
    ledger.save(rows("Werkstudent Marketing", "Werkstudent Content"))
    assert [r["title"] for r in ledger.load()] == ["Werkstudent Marketing", "Werkstudent Content"]
    assert [p.name for p in csv_path.parent.iterdir()] == ["seen_jobs.csv"]


def test_crash_mid_write_keeps_old_ledger(csv_path, monkeypatch):
    ledger.save(rows("Werkstudent Marketing"))
    before = csv_path.read_bytes()

    class Boom(ledger.csv.DictWriter):
        def writerows(self, rows):
            self.writerow(rows[0])
            raise KeyboardInterrupt  # e.g. the scheduled run is stopped halfway
    monkeypatch.setattr(ledger.csv, "DictWriter", Boom)
    with pytest.raises(KeyboardInterrupt):
        ledger.save(rows("Werkstudent Content", "Werkstudent PR"))
    assert csv_path.read_bytes() == before
    assert [p.name for p in csv_path.parent.iterdir()] == ["seen_jobs.csv"]
