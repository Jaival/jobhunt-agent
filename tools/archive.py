"""Sort application folders into drafts, applications/_sent/ and applications/_archive/ (engine/tools/appdirs.py).

Rules (every move is printed so the daily brief can list it):
    to _sent/      a draft that has a tracker row (sent)
    to _archive/   tracker Status "Rejected"; cold (2 follow-ups, the last one 7+ days old, no response);
                   an unsent draft with a **Closed:** line in job.md; an unsent draft older than 14 days
    back to _sent/ an archived folder whose tracker row now shows a response that isn't a rejection,
                   an interview date or Status "Interview"/"Offer"
Archived folders get an "**Archived:** <date>, <reason>" line under the title of job.md.

Usage (from the JobHunt folder):
    python engine/tools/archive.py auto [--dry-run]                   apply the rules above
    python engine/tools/archive.py archive <folder> --reason "..."      archive one folder by hand
    python engine/tools/archive.py restore <folder> [--to drafts|sent] [--reason "..."]
"""
import argparse
import datetime as dt
import sys

import openpyxl

import appdirs as A

XLSX = A.ROOT / "tracker" / "Job_Application_Tracker.xlsx"
DRAFT_DAYS = 14
COLD_WAIT_DAYS = 7


def as_date(v):
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    if isinstance(v, str):
        for f in ("%Y-%m-%d", "%d.%m.%Y"):
            try:
                return dt.datetime.strptime(v.strip(), f).date()
            except ValueError:
                pass
    return None


def tracker_rows():
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    it = wb["Applications"].iter_rows(values_only=True)
    hdr = [str(h).strip() if h else "" for h in next(it)]
    rows = {}
    for r in it:
        if not r or not r[0]:
            continue
        d = dict(zip(hdr, r))
        for key in ("CV Doc", "Cover Letter Doc", "Job ID"):
            name = A.name_from_path(d.get(key))
            if name:
                rows.setdefault(name, d)
                break
    wb.close()
    return rows


def closed_line(folder):
    job = folder / "job.md"
    if not job.exists():
        return None
    for line in job.read_text(encoding="utf-8", errors="replace").split("\n")[:8]:
        if line.startswith("**Closed:**"):
            return line[len("**Closed:**"):].strip()
    return None


def decide(bucket, folder, row, today):
    """Return (target_bucket, reason) or None."""
    if row:
        status = (row.get("Status") or "").strip()
        resp = as_date(row.get("Response Date"))
        if status == "Rejected":
            return ("archive", f"rejected {resp:%d.%m.%Y}" if resp else "rejected") if bucket != "archive" else None
        replied = status in ("Interview", "Offer") or as_date(row.get("Interview Date")) or resp
        if bucket == "archive":
            return ("sent", "reply or interview after archiving") if replied else None
        fus = A.followups_for(folder)
        if status == "Applied" and not resp and len(fus) >= 2:
            last = as_date(fus[-1].name[:10])
            if last and (today - last).days >= COLD_WAIT_DAYS:
                return "archive", f"cold: 2 follow-ups, last on {last:%d.%m.%Y}, no reply"
        return ("sent", "in the tracker (sent)") if bucket == "drafts" else None
    if bucket != "drafts":
        return None
    closed = closed_line(folder)
    if closed:
        return "archive", f"closed: {closed}"
    created = as_date(folder.name[:10])
    if created and (today - created).days > DRAFT_DAYS:
        return "archive", f"unsent draft, {(today - created).days} days old"
    return None


def apply(folder, target, reason, today, dry):
    label = {"archive": "_archive/", "sent": "_sent/", "drafts": "applications/"}[target]
    print(f"{'WOULD MOVE' if dry else 'MOVED'} {folder.name} -> {label} ({reason})")
    if dry:
        return
    was_archived = A.bucket_of(folder) == "archive"
    new = A.move(folder, target)
    if target == "archive":
        A.mark(new, "Archived", f"{today:%d.%m.%Y}, {reason}")
    elif was_archived:
        A.mark(new, "Restored", f"{today:%d.%m.%Y}, {reason}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("auto"); p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("archive"); p.add_argument("folder"); p.add_argument("--reason", required=True)
    p = sub.add_parser("restore"); p.add_argument("folder"); p.add_argument("--to", choices=["drafts", "sent"])
    p.add_argument("--reason", default="restored by hand")
    a = ap.parse_args()
    today = dt.date.today()

    if a.cmd == "auto":
        rows = tracker_rows()
        moves = 0
        for bucket, folder in list(A.iter_folders()):
            d = decide(bucket, folder, rows.get(folder.name), today)
            if d:
                apply(folder, d[0], d[1], today, a.dry_run)
                moves += 1
        print(f"{moves} move(s){' (dry run)' if a.dry_run else ''}")
        return 0

    folder = A.find(a.folder)
    if not folder:
        print(f"FAILED: no folder named {a.folder}", file=sys.stderr)
        return 1
    if a.cmd == "archive":
        apply(folder, "archive", a.reason, today, False)
    else:
        target = a.to or ("sent" if folder.name in tracker_rows() else "drafts")
        apply(folder, target, a.reason, today, False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
