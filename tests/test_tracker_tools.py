"""The tracker and folder tools: add_applied.py (the Excel row), archive.py (folder moves), tracker_to_md.py."""
import datetime as dt
import shutil

import openpyxl
import pytest

from conftest import ENGINE

TODAY = dt.date.today()
TRACKER = "tracker/Job_Application_Tracker.xlsx"
JOB_MD = """# Werkstudent Marketing (m/w/d)

- **Company:** Acme GmbH, Mannheim
- **Location:** Mannheim (hybrid)
- **Source:** Arbeitsagentur
- **Fit score:** 78
- **German required:** B2
- **Match reasons:** social media, analytics
- **Gaps:** no SEO tool experience
- **URL:** https://jobs.example/acme/1
"""


def day(offset):
    return f"{TODAY + dt.timedelta(days=offset):%Y-%m-%d}"


@pytest.fixture
def ws(sample):
    """The sample workspace with the template tracker and no application folders."""
    (sample / "tracker").mkdir()
    shutil.copy2(ENGINE / "templates" / "workspace" / TRACKER, sample / TRACKER)
    shutil.rmtree(sample / "applications")
    (sample / "applications").mkdir()
    return sample


def draft(ws, name, job_md=JOB_MD, bucket=""):
    folder = ws / "applications" / bucket / name
    folder.mkdir(parents=True)
    (folder / "job.md").write_text(job_md, encoding="utf-8")
    return folder


def rows(ws):
    wb = openpyxl.load_workbook(ws / TRACKER)
    data = list(wb["Applications"].iter_rows(values_only=True))
    wb.close()
    return [dict(zip(data[0], r)) for r in data[1:] if r[0]]


def set_cells(ws, job_id, **cells):
    """Change cells of the tracker row with this Job ID (as the candidate would in Excel)."""
    wb = openpyxl.load_workbook(ws / TRACKER)
    sheet = wb["Applications"]
    col = {c.value: i + 1 for i, c in enumerate(sheet[1])}
    row = next(r for r in range(2, sheet.max_row + 1) if sheet.cell(r, col["Job ID"]).value == job_id)
    for name, value in cells.items():
        sheet.cell(row, col[name.replace("_", " ")]).value = value
    wb.save(ws / TRACKER)


def sent(tool, ws, name, *args):
    """A draft added to the tracker (and moved to _sent/) by add_applied.py."""
    draft(ws, name)
    r = tool("add_applied.py", f"applications/{name}", *args)
    assert r.returncode == 0, r.stderr
    return r


def test_template_tracker_has_the_expected_header(ws):
    assert rows(ws) == []
    wb = openpyxl.load_workbook(ws / TRACKER)
    header = next(wb["Applications"].iter_rows(values_only=True))
    wb.close()
    assert header[:3] == ("Job ID", "Date", "Status")
    assert "Response Date" in header and "Interview Date" in header


# ---------- add_applied.py ----------

def test_add_applied_writes_the_row_and_moves_the_folder(tool, ws):
    name = f"{day(-2)}_Acme_Werkstudent-Marketing"
    draft(ws, name)
    r = tool("add_applied.py", f"applications/{name}", "--date", day(0), "--via", "Email", "--note", "n")
    assert r.returncode == 0, r.stderr
    assert "OK row 2: Acme GmbH | Werkstudent Marketing (m/w/d) | applied" in r.stdout
    assert f"MOVED {name} -> _sent/" in r.stdout
    assert (ws / "applications" / "_sent" / name).is_dir()
    assert not (ws / "applications" / name).exists()
    [row] = rows(ws)
    assert row["Job ID"] == name and row["Status"] == "Applied" and row["Company"] == "Acme GmbH"
    # german() keeps its lower-case match for every level except C1+, so "B2" is written as "b2"
    assert row["Fit Score"] == 78 and row["German Required"] == "b2"
    assert row["Job URL"] == "https://jobs.example/acme/1"
    assert row["Applied Via"] == "Email" and row["Notes"] == "n"
    assert row["CV Doc"].startswith(f"applications/_sent/{name}")
    assert f"{TODAY + dt.timedelta(days=7):%d.%m.%Y}" in row["Next Step"]
    assert list((ws / "backups" / day(0)).glob("Job_Application_Tracker_before-*.xlsx"))
    assert (ws / "tracker" / "applications.md").exists()


def test_add_applied_skips_a_folder_already_in_the_tracker(tool, ws):
    name = f"{day(-2)}_Acme_Werkstudent-Marketing"
    sent(tool, ws, name)
    r = tool("add_applied.py", name)
    assert r.returncode == 0, r.stderr
    assert r.stdout.startswith("SKIP: ")
    assert len(rows(ws)) == 1


def test_add_applied_refuses_while_excel_has_the_tracker_open(tool, ws):
    name = f"{day(-2)}_Acme_Werkstudent-Marketing"
    draft(ws, name)
    (ws / "tracker" / "~$Job_Application_Tracker.xlsx").write_text("", encoding="utf-8")
    r = tool("add_applied.py", f"applications/{name}")
    assert r.returncode == 1
    assert "lock file found" in r.stderr
    assert rows(ws) == []
    assert (ws / "applications" / name).is_dir()


def test_add_applied_reports_an_unknown_folder(tool, ws):
    r = tool("add_applied.py", "applications/2026-01-01_Nope_X")
    assert r.returncode == 1
    assert "no application folder named" in r.stderr


def test_add_applied_second_row_goes_below_the_first(tool, ws):
    first, second = f"{day(-2)}_Acme_Werkstudent-Marketing", f"{day(-1)}_Beta_Praktikum-Sales"
    sent(tool, ws, first)
    sent(tool, ws, second)
    assert [r["Job ID"] for r in rows(ws)] == [first, second]


# ---------- archive.py ----------

def test_auto_archives_a_rejected_application(tool, ws):
    name = f"{day(-2)}_Acme_Werkstudent-Marketing"
    sent(tool, ws, name)
    set_cells(ws, name, Status="Rejected")
    r = tool("archive.py", "auto")
    assert r.returncode == 0, r.stderr
    assert f"MOVED {name} -> _archive/ (rejected)" in r.stdout
    folder = ws / "applications" / "_archive" / name
    assert folder.is_dir()
    lines = (folder / "job.md").read_text(encoding="utf-8").split("\n")
    assert any(line.startswith("**Archived:**") for line in lines)
    assert "0 move(s)" in tool("archive.py", "auto").stdout


def test_auto_archives_an_old_or_closed_draft_and_keeps_a_fresh_one(tool, ws):
    old, closed, fresh = f"{day(-20)}_Old_Role", f"{day(-1)}_Shut_Role", f"{day(-1)}_Fresh_Role"
    draft(ws, old)
    lines = JOB_MD.split("\n")
    lines.insert(2, "**Closed:** page gone")
    draft(ws, closed, "\n".join(lines))
    draft(ws, fresh)
    r = tool("archive.py", "auto")
    assert r.returncode == 0, r.stderr
    archive = ws / "applications" / "_archive"
    assert (archive / old).is_dir() and (archive / closed).is_dir()
    assert f"MOVED {old} -> _archive/ (unsent draft" in r.stdout
    assert f"MOVED {closed} -> _archive/ (closed: page gone)" in r.stdout
    assert (ws / "applications" / fresh).is_dir()


def test_auto_archives_a_cold_application(tool, ws):
    name = f"{day(-25)}_Acme_Werkstudent-Marketing"
    sent(tool, ws, name, "--date", day(-20))
    (ws / "follow-ups").mkdir()
    for offset in (-14, -8):
        (ws / "follow-ups" / f"{day(offset)}_Acme.md").write_text("Follow-up\n", encoding="utf-8")
    r = tool("archive.py", "auto")
    assert r.returncode == 0, r.stderr
    assert "cold: 2 follow-ups" in r.stdout
    assert (ws / "applications" / "_archive" / name).is_dir()


def test_auto_brings_an_archived_application_back_after_an_interview(tool, ws):
    name = f"{day(-2)}_Acme_Werkstudent-Marketing"
    sent(tool, ws, name)
    set_cells(ws, name, Status="Rejected")
    tool("archive.py", "auto")
    assert (ws / "applications" / "_archive" / name).is_dir()
    set_cells(ws, name, Status="Interview")
    r = tool("archive.py", "auto")
    assert "-> _sent/ (reply or interview after archiving)" in r.stdout
    assert (ws / "applications" / "_sent" / name).is_dir()


def test_dry_run_moves_nothing(tool, ws):
    old = f"{day(-20)}_Old_Role"
    draft(ws, old)
    r = tool("archive.py", "auto", "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "WOULD MOVE" in r.stdout and "1 move(s) (dry run)" in r.stdout
    assert (ws / "applications" / old).is_dir()


def test_archive_and_restore_by_hand(tool, ws):
    name = f"{day(-1)}_Acme_Werkstudent-Marketing"
    draft(ws, name)
    assert tool("archive.py", "archive", name, "--reason", "by hand").returncode == 0
    assert (ws / "applications" / "_archive" / name).is_dir()
    assert tool("archive.py", "restore", name, "--to", "drafts").returncode == 0
    folder = ws / "applications" / name
    assert folder.is_dir()
    lines = (folder / "job.md").read_text(encoding="utf-8").split("\n")
    assert any(line.startswith("**Restored:**") for line in lines)


# ---------- tracker_to_md.py ----------

def test_tracker_to_md_lists_sent_and_drafts(tool, ws):
    sent(tool, ws, f"{day(-2)}_Acme_Werkstudent-Marketing")
    fresh = f"{day(-1)}_Beta_Praktikum-Sales"
    draft(ws, fresh)
    r = tool("tracker_to_md.py")
    assert r.returncode == 0, r.stderr
    md = (ws / "tracker" / "applications.md").read_text(encoding="utf-8")
    assert md.startswith("# Applications (generated, do not edit)")
    assert "## Sent applications (1: Applied 1)" in md and "Acme GmbH" in md
    assert fresh in (ws / "applications" / "INDEX.md").read_text(encoding="utf-8")


# ---------- safe writes and tracker.py status ----------

def test_add_applied_does_not_confuse_a_folder_with_a_longer_name(tool, ws):
    sent(tool, ws, f"{day(-2)}_Acme_Data-Engineer")
    name = f"{day(-2)}_Acme_Data"
    r = sent(tool, ws, name)
    assert "OK row 3" in r.stdout and "SKIP" not in r.stdout
    assert [row["Job ID"] for row in rows(ws)][1] == name


def test_add_applied_leaves_no_temp_file_and_a_readable_tracker(tool, ws):
    sent(tool, ws, f"{day(-2)}_Acme_Werkstudent-Marketing")
    assert list((ws / "tracker").glob("*.tmp")) == []
    assert len(rows(ws)) == 1


def test_status_records_a_rejection(tool, ws):
    name = f"{day(-2)}_Acme_Werkstudent-Marketing"
    sent(tool, ws, name)
    r = tool("tracker.py", "status", name, "--status", "Rejected", "--response-date", day(0), "--note", "mail of today")
    assert r.returncode == 0, r.stderr
    assert r.stdout.startswith("OK row 2: ")
    [row] = rows(ws)
    assert row["Status"] == "Rejected" and row["Response Date"].date() == TODAY
    assert row["Notes"].endswith("mail of today")
    assert list((ws / "backups" / day(0)).glob("*status-*.xlsx"))
    assert "-> _archive/ (rejected" in tool("archive.py", "auto").stdout


def test_status_records_an_interview(tool, ws):
    name = f"{day(-2)}_Acme_Werkstudent-Marketing"
    sent(tool, ws, name)
    r = tool("tracker.py", "status", name, "--status", "Interview", "--response-date", day(0),
             "--interview-date", day(5))
    assert r.returncode == 0, r.stderr
    [row] = rows(ws)
    assert row["Status"] == "Interview"
    assert row["Response Date"].date() == TODAY
    assert row["Interview Date"].date() == TODAY + dt.timedelta(days=5)


def test_status_refuses_while_excel_has_the_tracker_open(tool, ws):
    name = f"{day(-2)}_Acme_Werkstudent-Marketing"
    sent(tool, ws, name)
    (ws / "tracker" / "~$Job_Application_Tracker.xlsx").write_text("", encoding="utf-8")
    r = tool("tracker.py", "status", name, "--status", "Rejected")
    assert r.returncode == 1
    assert "lock file found" in r.stderr
    assert rows(ws)[0]["Status"] == "Applied"


def test_status_reports_a_folder_without_a_row(tool, ws):
    name = f"{day(-1)}_Acme_Werkstudent-Marketing"
    draft(ws, name)
    r = tool("tracker.py", "status", name, "--status", "Rejected")
    assert r.returncode == 1
    assert "isn't in the tracker" in r.stderr


def test_status_rejects_an_unknown_status_or_date(tool, ws):
    name = f"{day(-2)}_Acme_Werkstudent-Marketing"
    sent(tool, ws, name)
    assert tool("tracker.py", "status", name, "--status", "Maybe").returncode == 2
    r = tool("tracker.py", "status", name, "--status", "Rejected", "--response-date", "09.11.2026")
    assert r.returncode != 0
    [row] = rows(ws)
    assert row["Status"] == "Applied" and row["Response Date"] is None
