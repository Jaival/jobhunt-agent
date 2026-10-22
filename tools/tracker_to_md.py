"""Write tracker/applications.md (read-only view of the Excel tracker plus unsent drafts) and
applications/INDEX.md (what to act on: drafts, sent applications, archive counts).

The Excel file stays the only master copy. This script only reads it. Folders are found in
applications/, applications/_sent/ and applications/_archive/ (engine/tools/appdirs.py).
Usage (from the JobHunt folder): python engine/tools/tracker_to_md.py
"""
import datetime as dt
import re
import sys

import openpyxl

import appdirs as A

ROOT = A.ROOT
XLSX = ROOT / "tracker" / "Job_Application_Tracker.xlsx"
OUT = ROOT / "tracker" / "applications.md"
INDEX = A.APPS / "INDEX.md"
CADENCE_DAYS = 7  # career-ops-playbook.md section F
MAX_FOLLOWUPS = 2
RECENT_DAYS = 14


def as_date(value):
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
            try:
                return dt.datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                pass
    return None


def fmt(d):
    return d.strftime("%d.%m.%Y") if d else ""


def cell(value):
    text = "" if value is None else str(value)
    return text.replace("|", "/").replace("\n", " ").strip()


def folder_of(row):
    for key in ("CV Doc", "Cover Letter Doc", "Job ID"):
        name = A.name_from_path(row.get(key))
        if name:
            return name
    return None


def read_job_md(path):
    info = {"title": path.name if path else "", "score": "", "role_type": "", "closed": "", "archived": ""}
    job = path / "job.md" if path else None
    if not job or not job.exists():
        return info
    text = job.read_text(encoding="utf-8", errors="replace")
    for key, pat in (("title", r"^# (.+)$"), ("score", r"\*\*Fit score:\*\*\s*(\d+)"),
                     ("role_type", r"\*\*Role type:\*\*\s*([^\n]+)"), ("closed", r"^\*\*Closed:\*\*\s*([^\n]+)"),
                     ("archived", r"^\*\*Archived:\*\*\s*([^\n]+)")):
        m = re.search(pat, text, re.M)
        if m:
            info[key] = m.group(1).strip()
    return info


def next_action(path):
    """First sentence of the 'Apply via' line in outreach.md, for INDEX.md."""
    o = path / "outreach.md"
    if not o.exists():
        return ""
    m = re.search(r"\*\*Apply via:\*\*\s*([^\n]+)", o.read_text(encoding="utf-8", errors="replace"))
    if not m:
        return ""
    text = re.split(r"(?<=[a-z)])\.\s", m.group(1), maxsplit=1)[0]
    return cell(text[:110] + ("…" if len(text) > 110 else ""))


def link(path, base):
    """Markdown link to a folder's job.md, relative to the directory of the output file."""
    if not path:
        return ""
    rel = (path / "job.md").relative_to(ROOT).as_posix()
    prefix = "../" if base == "tracker" else ""
    if base == "apps":
        rel = rel[len("applications/"):]
    return f"[{A.bucket_of(path)}]({prefix}{rel})".replace(" ", "%20")


def main():
    today = dt.date.today()
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    rows = wb["Applications"].iter_rows(values_only=True)
    header = [str(h).strip() if h else "" for h in next(rows)]
    sent = [dict(zip(header, r)) for r in rows if r and r[0]]
    wb.close()

    folders = {d.name: (b, d) for b, d in A.iter_folders()}
    sent_names = {f for f in (folder_of(r) for r in sent) if f}

    # ---------- tracker/applications.md ----------
    lines = [
        "# Applications (generated, do not edit)", "",
        f"Generated {fmt(today)} from tracker/Job_Application_Tracker.xlsx by engine/tools/tracker_to_md.py.",
        "Edit the Excel file, or tell Claude what changed. This file is overwritten on every run.",
        "Folders: drafts in `applications/`, sent in `applications/_sent/`, finished in `applications/_archive/`. "
        "Action view: `applications/INDEX.md`.", "",
    ]
    status_count = {}
    for r in sent:
        status_count[r.get("Status") or "?"] = status_count.get(r.get("Status") or "?", 0) + 1
    summary = ", ".join(f"{k} {v}" for k, v in sorted(status_count.items()))
    lines += [f"## Sent applications ({len(sent)}: {summary})", "",
              "| Applied | Company | Role | Score | Status | Follow-ups | Next follow-up | Response | Interview | Contact | Next step | Folder |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    due, sent_info = [], []
    for r in sorted(sent, key=lambda r: as_date(r.get("Applied On")) or dt.date.min, reverse=True):
        applied, response = as_date(r.get("Applied On")), as_date(r.get("Response Date"))
        name = folder_of(r)
        path = folders.get(name, (None, None))[1] if name else None
        fu = [as_date(f.name[:10]) for f in A.followups_for(path)] if path else []
        nxt = ""
        if r.get("Status") == "Applied" and not response and applied:
            if len(fu) >= MAX_FOLLOWUPS:
                cold_on = fu[-1] + dt.timedelta(days=CADENCE_DAYS)
                nxt = "cold" if cold_on <= today else f"cold from {fmt(cold_on)}"
            else:
                nd = (fu[-1] if fu else applied) + dt.timedelta(days=CADENCE_DAYS)
                nxt = fmt(nd) + (" (due)" if nd <= today else "")
                if nd <= today:
                    due.append(cell(r.get("Company")))
        sent_info.append((r, path, nxt))
        lines.append("| " + " | ".join([
            fmt(applied), cell(r.get("Company")), cell(r.get("Title")), cell(r.get("Fit Score")),
            cell(r.get("Status")), str(len(fu)), nxt, fmt(response),
            fmt(as_date(r.get("Interview Date"))), cell(r.get("Contact Person")), cell(r.get("Next Step")),
            link(path, "tracker"),
        ]) + " |")
    lines.append("")
    if due:
        lines += [f"Follow-up due: {', '.join(due)}.", ""]

    drafts = []
    for name, (bucket, path) in folders.items():
        if bucket == "drafts" and name not in sent_names:
            drafts.append((as_date(name[:10]), name, path, read_job_md(path)))
    drafts.sort(key=lambda x: (x[0] or dt.date.min, x[1]), reverse=True)

    def draft_rows(items):
        out = ["| Drafted | Age | Company | Role | Type | Score | Status | Folder |",
               "|---|---|---|---|---|---|---|---|"]
        for created, name, path, info in items:
            age = f"{(today - created).days} d" if created else ""
            status = f"closed: {cell(info['closed'])}" if info["closed"] else "open / not sent"
            out.append("| " + " | ".join([
                fmt(created), age, cell(A.company_token(name) or ""), cell(info["title"]),
                cell(info["role_type"]), info["score"], status, link(path, "tracker"),
            ]) + " |")
        return out

    recent = [x for x in drafts if x[0] and (today - x[0]).days <= RECENT_DAYS]
    older = [x for x in drafts if x not in recent]
    lines += [f"## Drafts not sent yet ({len(drafts)}; {len(recent)} from the last {RECENT_DAYS} days)", ""]
    lines += draft_rows(recent) + [""]
    if older:
        lines += [f"<details><summary>Older drafts ({len(older)})</summary>", ""]
        lines += draft_rows(older) + ["", "</details>", ""]

    archived = [(name, path, read_job_md(path)) for name, (b, path) in folders.items() if b == "archive"]
    by_month = {}
    for name, path, info in archived:
        reason = info["archived"].split(", ", 1)[1] if ", " in info["archived"] else (info["archived"] or "archived")
        kind = next((k for k in ("rejected", "cold", "closed", "unsent draft") if reason.startswith(k)), "other")
        m = name[:7]
        by_month.setdefault(m, {}).setdefault(kind, 0)
        by_month[m][kind] += 1
    lines += [f"## Archived ({len(archived)})", ""]
    for m in sorted(by_month, reverse=True):
        lines.append(f"- **{m}:** " + ", ".join(f"{k} {v}" for k, v in sorted(by_month[m].items())))
    if archived:
        lines += ["", f"<details><summary>All archived folders ({len(archived)})</summary>", ""]
        lines += [f"- {link(path, 'tracker')} {name}: {cell(info['archived'])}" for name, path, info in sorted(archived, reverse=True)]
        lines += ["", "</details>"]
    lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")

    # ---------- applications/INDEX.md ----------
    ix = ["# Application folders (generated, do not edit)", "",
          f"Generated {fmt(today)} by engine/tools/tracker_to_md.py. Drafts live here, sent applications in `_sent/`, "
          "finished ones in `_archive/` (engine/tools/archive.py moves them). Full record: `tracker/applications.md`.", "",
          f"## Drafts to send ({len(drafts)})", "",
          "| Drafted | Age | Company | Role | Score | Next action | Folder |", "|---|---|---|---|---|---|---|"]
    for created, name, path, info in drafts:
        age = f"{(today - created).days} d" if created else ""
        action = f"closed: {cell(info['closed'])}" if info["closed"] else next_action(path)
        ix.append("| " + " | ".join([fmt(created), age, cell(A.company_token(name) or ""), cell(info["title"]),
                                       info["score"], action, link(path, "apps")]) + " |")
    open_sent = [(r, p, n) for r, p, n in sent_info if r.get("Status") != "Rejected" and p and A.bucket_of(p) == "sent"]
    interviews = [x for x in open_sent if x[0].get("Status") in ("Interview", "Offer") or as_date(x[0].get("Interview Date"))]
    rest = [x for x in open_sent if x not in interviews]
    ix += ["", f"## Sent, waiting for an answer ({len(open_sent)}; {len(interviews)} interview)", "",
           "| Applied | Company | Role | Status | Next follow-up | Folder |", "|---|---|---|---|---|---|"]
    for r, path, nxt in interviews + rest:
        status = cell(r.get("Status")) + (f", interview {fmt(as_date(r.get('Interview Date')))}" if as_date(r.get("Interview Date")) else "")
        ix.append("| " + " | ".join([fmt(as_date(r.get("Applied On"))), cell(r.get("Company")), cell(r.get("Title")),
                                       status, nxt, link(path, "apps")]) + " |")
    ix += ["", f"## Archive ({len(archived)})", ""]
    ix += [f"- **{m}:** " + ", ".join(f"{k} {v}" for k, v in sorted(by_month[m].items())) for m in sorted(by_month, reverse=True)]
    ix.append("")
    INDEX.write_text("\n".join(ix), encoding="utf-8")

    print(f"Wrote {OUT.relative_to(ROOT)} and {INDEX.relative_to(ROOT)}: {len(sent)} sent, {len(drafts)} unsent drafts, "
          f"{len(archived)} archived, follow-ups due: {len(due)}")


if __name__ == "__main__":
    sys.exit(main())
