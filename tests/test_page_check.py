"""build_application.py: the page limits are checked before the final files exist, and temp files never stay."""
import json
import os
import subprocess
import sys
from fnmatch import fnmatch

from conftest import TOOLS
from test_sample_workspace import APP

# argv: tools dir, application folder, JSON {"cv": pages, "letter": pages} or {"raise": "pdf" | "process"}
SCRIPT = r"""
import json, subprocess, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
plan = json.loads(sys.argv[3])
sys.argv = ["build_application.py", sys.argv[2]]
import pypdf
import build_application as b

def fake_export(files, setting="auto"):
    if plan.get("raise") == "pdf":
        raise b.pdf_export.PdfError("no PDF engine found")
    if plan.get("raise") == "process":
        raise subprocess.CalledProcessError(1, ["soffice"])
    for f in files:
        w = pypdf.PdfWriter()
        for _ in range(plan["cv" if "CV" in Path(f).name else "letter"]):
            w.add_blank_page(width=200, height=200)
        with open(Path(f).with_suffix(".pdf"), "wb") as out:
            w.write(out)
    return "word"

b.pdf_export.export = fake_export
sys.exit(b.main())
"""


def build(sample, plan):
    env = {**os.environ, "JOBHUNT_ROOT": str(sample), "PYTHONIOENCODING": "utf-8", "JOBHUNT_OFFLINE": "1"}
    return subprocess.run([sys.executable, "-c", SCRIPT, str(TOOLS), APP, json.dumps(plan)], cwd=sample, env=env,
                          capture_output=True, text=True, encoding="utf-8")


def files(sample):
    return sorted(p.name for p in (sample / APP).iterdir() if p.suffix in (".docx", ".pdf"))


def count(names, pattern):
    return len([n for n in names if fnmatch(n, pattern)])


def test_pages_within_limits_gives_final_docx_and_pdf(sample):
    r = build(sample, {"cv": 2, "letter": 1})
    assert r.returncode == 0, r.stderr
    names = files(sample)
    assert len(names) == 4, names
    for pattern in ("*_CV_*.docx", "*_CV_*.pdf", "*_Cover_Letter_*.docx", "*_Cover_Letter_*.pdf"):
        assert count(names, pattern) == 1, (pattern, names)
    assert not any(n.startswith("~build_") for n in names)


def test_too_many_pages_writes_no_final_file(sample):
    r = build(sample, {"cv": 3, "letter": 1})
    assert r.returncode == 1
    assert "page check:" in r.stderr
    assert "CV has 3 pages (max 2)" in r.stderr
    assert files(sample) == []


def test_letter_over_one_page_fails_too(sample):
    r = build(sample, {"cv": 2, "letter": 2})
    assert r.returncode == 1
    assert "~build_" not in r.stderr
    assert files(sample) == []


def test_no_pdf_engine_still_builds_the_docx(sample):
    r = build(sample, {"raise": "pdf"})
    assert r.returncode == 0, r.stderr
    assert "WARNING" in r.stderr and "page limits unchecked" in r.stderr
    names = files(sample)
    assert count(names, "*_CV_*.docx") == 1 and count(names, "*_Cover_Letter_*.docx") == 1
    assert not any(n.endswith(".pdf") for n in names)
    assert not any(n.startswith("~build_") for n in names)


def test_a_failing_pdf_engine_is_reported_like_a_missing_one(sample):
    r = build(sample, {"raise": "process"})
    assert r.returncode == 0, r.stderr
    assert "WARNING" in r.stderr and "no PDFs" in r.stderr
    assert "Traceback" not in r.stderr
    names = files(sample)
    assert count(names, "*_CV_*.docx") == 1 and count(names, "*_Cover_Letter_*.docx") == 1
    assert not any(n.startswith("~build_") for n in names)


def test_a_wrong_date_format_fails_cleanly(tool, sample):
    md = sample / APP / "application.md"
    lines = md.read_text(encoding="utf-8").split("\n")
    end = lines.index("---", 1)
    dates = [i for i in range(1, end) if lines[i].startswith("date:")]
    if dates:
        lines[dates[0]] = "date: 19.10.2026"
    else:
        lines.insert(1, "date: 19.10.2026")
    md.write_text("\n".join(lines), encoding="utf-8")
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 1
    assert r.stderr.startswith("FAILED")
    assert "YYYY-MM-DD" in r.stderr
    assert "Traceback" not in r.stderr
    assert files(sample) == []
