"""End to end on the fictional sample workspace: setup check, CV map, builder (without PDFs), ATS scan."""
import json

import docx

APP = "applications/2026-10-23_Example-Company_Working-Student-Marketing"


def texts(path):
    return [p.text for p in docx.Document(str(path)).paragraphs]


def test_setup_check_ready(tool):
    r = tool("setup_check.py", "--init", "--json")
    result = json.loads(r.stdout)
    todo = [c for c in result["checks"] if c["status"] == "todo"]
    assert result["ready"], todo
    assert any(c["item"] == "CV map matches the master CV and letter" and c["status"] == "ok"
               for c in result["checks"])


def test_cv_map_check(tool):
    r = tool("cv_map.py", "check")
    assert r.returncode == 0, r.stdout
    assert "section projects: ['Campus Café Campaign', 'Newsletter Relaunch', 'Study Talk Podcast']" in r.stdout
    assert "section skills: ['Content', 'Social media', 'Analytics', 'Languages']" in r.stdout


def test_build(tool, sample):
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 0, r.stderr
    folder = sample / APP
    cv = texts(folder / "Lena_Fischer_CV_Example-Company.docx")
    assert cv[1] == "Social Media & Content Student | Instagram, LinkedIn & Analytics"
    bullets = [t for t in cv if t.startswith("- ")]
    assert bullets == ["- Planned and published three social media posts a week for four clients.",
                       "- Wrote first drafts of two client newsletters a month.",
                       "- Built a monthly reporting sheet in Google Sheets that the account team still uses."]
    titles = ["Campus Café Campaign", "Study Talk Podcast", "Newsletter Relaunch"]
    assert [t for t in cv if t in titles] == titles
    podcast = cv.index("Study Talk Podcast")
    assert cv[podcast + 1].startswith("Six interview episodes")      # each project moves with its text
    skills = [t.split(":")[0] for t in cv[cv.index("SKILLS") + 1:cv.index("EDUCATION")] if ":" in t]
    assert skills == ["Social media", "Analytics", "Content", "Languages"]
    assert cv[-1].startswith("B.A. Media and Communication")       # untouched parts stay

    letter = texts(folder / "Lena_Fischer_Cover_Letter_Example-Company.docx")
    assert "Mannheim, 23.10.2026" in letter
    assert "Dear Example Company team," in letter
    assert not any("replaced by the letter text" in t for t in letter)
    body = letter[letter.index("Dear Example Company team,") + 1:letter.index("Kind regards,")]
    assert len([t for t in body if t]) == 5


def test_build_refuses_unmapped_section(tool, sample):
    app = sample / APP / "application.md"
    app.write_text(app.read_text(encoding="utf-8").replace("  skills:", "  abilities:"), encoding="utf-8")
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 1 and "unknown cv keys ['abilities']" in r.stderr


def test_student_letter_checks(tool, sample):
    app = sample / APP / "application.md"
    app.write_text(app.read_text(encoding="utf-8").replace("as soon as possible", "soon"), encoding="utf-8")
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 1 and "as soon as possible" in r.stderr


def test_broken_map_warns_and_stops_building(tool, sample):
    layout = sample / "cv" / "layout.yaml"
    layout.write_text(layout.read_text(encoding="utf-8").replace("start: PROJECTS", "start: PROJEKTE"),
                      encoding="utf-8")
    r = tool("cv_map.py", "check")
    assert r.returncode == 1 and "'projekte' found 0 times" in r.stdout
    result = json.loads(tool("setup_check.py", "--init", "--json").stdout)
    mapped = [c for c in result["checks"] if c["item"].startswith("CV map matches")]
    assert mapped[0]["status"] == "warn" and "remap my CV" in mapped[0]["fix"]
    assert result["ready"]                                          # a warning, not a blocker
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 1 and "remap my CV" in r.stderr


def test_layout_none(tool, sample):
    cfg = sample / "config.yaml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace("layout: cv/layout.yaml", "layout: none"),
                   encoding="utf-8")
    assert "drafts only" in tool("cv_map.py", "check").stdout
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 1 and "layout: none" in r.stderr


def test_ats_scan(tool, sample):
    r = tool("ats_scan.py", sample / "cv" / "Lena_Fischer_CV.docx", "--json")
    findings = json.loads(r.stdout)
    assert isinstance(findings, (list, dict))
    assert "must-fix" not in r.stdout                               # a plain single-column CV
