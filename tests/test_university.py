"""config.yaml `university`: a name or a list of names; a student letter must mention one of them."""
from test_grounding import edit
from test_sample_workspace import APP

LETTER = "B.A. in Media and Communication at Universität Mannheim"


def set_university(root, value):
    path = root / "config.yaml"
    text = path.read_text(encoding="utf-8")
    assert "university: Universität Mannheim" in text
    path.write_text(text.replace("university: Universität Mannheim", f"university: {value}", 1), encoding="utf-8")


def test_letter_without_the_university_fails(tool, sample):
    edit(sample, APP, LETTER, "B.A. in Media and Communication")
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 1 and "student letter must mention Universität Mannheim enrolment" in r.stderr


def test_any_name_from_the_list_passes(tool, sample):
    set_university(sample, "[Universität Mannheim, University of Mannheim]")
    edit(sample, APP, LETTER, "B.A. in Media and Communication at the University of Mannheim")
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 0, r.stderr


def test_list_names_every_variant_when_none_is_mentioned(tool, sample):
    set_university(sample, "[Universität Mannheim, University of Mannheim]")
    edit(sample, APP, LETTER, "B.A. in Media and Communication")
    r = tool("build_application.py", APP, "--no-pdf")
    assert "must mention Universität Mannheim or University of Mannheim enrolment" in r.stderr


def test_bad_value_is_refused(tool, sample):
    set_university(sample, "[Universität Mannheim, 3]")
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 1 and "university must be a name or a list of names" in r.stderr
