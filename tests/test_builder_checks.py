"""build_application.py checks: whole-document text, placeholders, unmapped letter parts, numbers with a unit."""
import json

import docx
import yaml

from test_sample_workspace import APP


def edit(root, app, old, new):
    path = root / app / "application.md"
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def test_text_in_a_footer_is_checked(tool, sample):
    master = sample / yaml.safe_load((sample / "config.yaml").read_text(encoding="utf-8"))["master_letter"]
    doc = docx.Document(str(master))
    doc.sections[0].footer.paragraphs[0].text = "Synergy [DATE]"
    doc.save(str(master))
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 1
    assert "contains '[' or ']'" in r.stderr


def test_an_angle_bracket_placeholder_fails(tool, sample):
    edit(sample, APP, "I am applying for the working student position", "I am applying for the <role at company> position")
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 1
    assert "placeholder" in r.stderr


def test_a_plain_less_than_sign_is_not_a_placeholder(tool, sample):
    edit(sample, APP, "good content starts with knowing who reads it.",
         "good content starts with knowing who reads it (a < b).")
    r = tool("build_application.py", APP, "--no-pdf")
    assert "placeholder" not in r.stderr


def test_an_unmapped_recipient_is_reported(tool, sample):
    layout = sample / "cv" / "layout.yaml"
    text = layout.read_text(encoding="utf-8")
    line = '  recipient: {starts_with: "Example Company"}\n'
    assert line in text
    layout.write_text(text.replace(line, ""), encoding="utf-8")
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 0, r.stderr
    assert "recipient is set in application.md but cv/layout.yaml maps no letter recipient" in r.stdout


def test_a_number_with_a_unit_suffix_is_checked(tool, sample):
    edit(sample, APP, "1,200 new followers", "10k new followers")
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 1
    assert "10k" in r.stderr


def test_a_number_from_the_ad_only_gets_a_warning(tool, sample):
    ad_file = sample / APP / "ad.json"
    ad = json.loads(ad_file.read_text(encoding="utf-8"))
    ad["tasks"][0] += ", team of 37"
    ad_file.write_text(json.dumps(ad, ensure_ascii=False, indent=2), encoding="utf-8")
    edit(sample, APP, "how I could support your team.", "how I could support your team of 37.")
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 0, r.stderr
    assert "numbers from the ad only, not in your files: 37" in r.stdout
