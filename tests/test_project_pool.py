"""Project pool (max: N + further in cv/layout.yaml): N projects stay as blocks, the others are named on one line."""
import copy

import docx

from test_sample_workspace import APP, texts

CV = "Lena_Fischer_CV_Example-Company.docx"
FURTHER = "Further projects: Blog"


def make_pool(sample, max_=2, further=True):
    """Add a 'Further projects' line after the projects and turn the projects section into a pool."""
    path = sample / "cv" / "Lena_Fischer_CV.docx"
    d = docx.Document(str(path))
    skills = next(p for p in d.paragraphs if p.text == "SKILLS")
    line = copy.deepcopy(skills._p)
    skills._p.addprevious(line)
    p = docx.text.paragraph.Paragraph(line, skills._parent)
    p.runs[0].text, p.runs[0].bold = FURTHER, False
    d.save(str(path))
    layout = sample / "cv" / "layout.yaml"
    pool = f"      max: {max_}\n" + (f'      further: {{starts_with: "Further projects"}}\n' if further else "")
    text = layout.read_text(encoding="utf-8").replace("      end: [SKILLS]\n", f'      end: ["{FURTHER}"]\n' + pool, 1)
    layout.write_text(text, encoding="utf-8")


def test_pool_names_the_rest(tool, sample):
    make_pool(sample, max_=2)
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 0, r.stderr
    cv = texts(sample / APP / CV)
    assert [t for t in cv if t in ("Campus Café Campaign", "Study Talk Podcast", "Newsletter Relaunch")] == \
        ["Campus Café Campaign", "Study Talk Podcast"]
    assert "Further projects: Newsletter Relaunch, Blog" in cv
    assert "named on the further line only: Newsletter Relaunch" in r.stdout


def test_pool_big_enough_changes_nothing(tool, sample):
    make_pool(sample, max_=3)
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 0, r.stderr
    assert FURTHER in texts(sample / APP / CV)


def test_pool_needs_a_further_line(tool, sample):
    make_pool(sample, further=False)
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 1 and "max needs further" in r.stderr


def test_cv_map_check_shows_the_pool(tool, sample):
    make_pool(sample, max_=2)
    r = tool("cv_map.py", "check")
    assert r.returncode == 0, r.stdout
    assert "section projects: shows 2 as blocks, names the rest on: Further projects: Blog" in r.stdout
