"""The Excel tracker (tracker/Job_Application_Tracker.xlsx): safe writes, and the `status` command.

The tracker is the candidate's only record of sent applications. Every write goes through here: it refuses to
run while Excel has the file open, copies a backup to backups/<today>/, and saves to a temp file that replaces
the tracker in one step, so the file is never half written.

Usage (from the JobHunt folder):
    python engine/tools/tracker.py status <folder> --status Rejected|Interview|Offer|Applied
                                [--response-date YYYY-MM-DD] [--interview-date YYYY-MM-DD] [--note "text"]
        Record a reply to a sent application (a rejection, an interview invitation, an offer), then refresh
        tracker/applications.md. <folder> is the application folder's name or path.
"""
import argparse
import datetime as dt
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import openpyxl

import appdirs
import atomic

from config import ROOT
XLSX = ROOT / "tracker" / "Job_Application_Tracker.xlsx"
LOCK = ROOT / "tracker" / "~$Job_Application_Tracker.xlsx"
STATUSES = ("Applied", "Interview", "Offer", "Rejected")
LOCKED = "FAILED: the tracker is open in Excel (lock file found). Close it and run again."


def locked():
    return LOCK.exists()


def backup(label):
    folder = ROOT / "backups" / f"{dt.date.today():%Y-%m-%d}"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"Job_Application_Tracker_before-{label}.xlsx"
    shutil.copy2(XLSX, path)
    return path


def save(wb):
    """Write the workbook to a temp file beside the tracker, check it opens, then swap it in."""
    fd, tmp = tempfile.mkstemp(prefix=".tracker.", suffix=".xlsx.tmp", dir=XLSX.parent)
    os.close(fd)
    try:
        wb.save(tmp)
        with open(tmp, "rb") as f:  # a file object, as openpyxl refuses a path that doesn't end in .xlsx
            openpyxl.load_workbook(f, read_only=True).close()
        atomic.replace(tmp, XLSX)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def refresh():
    subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "tracker_to_md.py")], check=True,
                   env={**os.environ, "JOBHUNT_ROOT": str(ROOT)})


def row_of(ws, col, name):
    """The row whose Job ID, CV Doc or Cover Letter Doc belongs to folder `name`, else None."""
    last = max(r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value)
    for r in range(2, last + 1):
        job_id = ws.cell(r, col["Job ID"]).value
        if job_id == name or appdirs.name_from_path(job_id) == name:
            return r
        if any(appdirs.name_from_path(ws.cell(r, col[h]).value) == name for h in ("CV Doc", "Cover Letter Doc")):
            return r
    return None


def cmd_status(a):
    folder = appdirs.find(a.folder)
    if not folder:
        print(f"FAILED: no application folder named {a.folder}", file=sys.stderr)
        return 1
    if locked():
        print(LOCKED, file=sys.stderr)
        return 1
    wb = openpyxl.load_workbook(XLSX)
    ws = wb["Applications"]
    col = {c.value: i + 1 for i, c in enumerate(ws[1])}
    r = row_of(ws, col, folder.name)
    if r is None:
        print(f"FAILED: {folder.name} isn't in the tracker (add it with add_applied.py first)", file=sys.stderr)
        return 1
    backup(f"status-{folder.name[11:40]}")
    ws.cell(r, col["Status"]).value = a.status
    done = a.status
    if a.response_date:
        ws.cell(r, col["Response Date"]).value = dt.datetime.combine(a.response_date, dt.time())
        done += f", response {a.response_date:%d.%m.%Y}"
    if a.interview_date:
        ws.cell(r, col["Interview Date"]).value = dt.datetime.combine(a.interview_date, dt.time())
        done += f", interview {a.interview_date:%d.%m.%Y}"
    if a.note:
        notes = ws.cell(r, col["Notes"])
        notes.value = f"{notes.value}; {a.note}" if notes.value else a.note
    save(wb)
    print(f"OK row {r}: {ws.cell(r, col['Company']).value} | {ws.cell(r, col['Title']).value} | {done}", flush=True)
    refresh()
    return 0


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # company names can hold characters outside the console code page
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("status")
    p.add_argument("folder")
    p.add_argument("--status", required=True, choices=STATUSES)
    p.add_argument("--response-date", type=dt.date.fromisoformat)
    p.add_argument("--interview-date", type=dt.date.fromisoformat)
    p.add_argument("--note", default="")
    a = ap.parse_args()
    return cmd_status(a)


if __name__ == "__main__":
    sys.exit(main())
