"""The letter's tagline line (letter.headline in cv/layout.yaml): letter_headline, else cv.headline."""
import copy

import docx

from test_grounding import edit
from test_sample_workspace import APP, texts

LETTER = "Lena_Fischer_Cover_Letter_Example-Company.docx"
CV_HEADLINE = "Social Media & Content Student | Instagram, LinkedIn & Analytics"


def add_tagline(sample, mapped=True):
    """Give the master letter a tagline under the name, and map it."""
    path = sample / "cv" / "Lena_Fischer_CoverLetter.docx"
    d = docx.Document(str(path))
    name = d.paragraphs[0]
    new = copy.deepcopy(name._p)
    name._p.addnext(new)
    docx.text.paragraph.Paragraph(new, name._parent).runs[0].text = "Marketing Student"
    d.save(str(path))
    if mapped:
        layout = sample / "cv" / "layout.yaml"
        layout.write_text(layout.read_text(encoding="utf-8").replace(
            "letter:\n", 'letter:\n  headline: {text: "Marketing Student"}\n', 1), encoding="utf-8")


def test_cv_headline_is_the_default(tool, sample):
    add_tagline(sample)
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 0, r.stderr
    assert texts(sample / APP / LETTER)[1] == CV_HEADLINE


def test_letter_headline_wins(tool, sample):
    add_tagline(sample)
    edit(sample, APP, "short: Example-Company", "short: Example-Company\nletter_headline: Social Media Student")
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 0, r.stderr
    assert texts(sample / APP / LETTER)[1] == "Social Media Student"


def test_unmapped_letter_headline_fails(tool, sample):
    add_tagline(sample, mapped=False)
    edit(sample, APP, "short: Example-Company", "short: Example-Company\nletter_headline: Social Media Student")
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 1 and "letter_headline is set but cv/layout.yaml maps no letter headline" in r.stderr


def test_letter_headline_is_grounded(tool, sample):
    add_tagline(sample)
    edit(sample, APP, "short: Example-Company", "short: Example-Company\nletter_headline: Marketing Student | 40% reach")
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 1 and "letter headline: not in your CV, CLAUDE.md, projects.md or the ad: 40%" in r.stderr


def test_cv_map_check_shows_the_letter_headline(tool, sample):
    add_tagline(sample)
    r = tool("cv_map.py", "check")
    assert r.returncode == 0, r.stdout
    assert "letter headline: Marketing Student" in r.stdout
