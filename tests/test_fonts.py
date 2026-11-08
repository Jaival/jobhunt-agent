"""Fonts in built documents: one family by default, or the master's own fonts with `font: keep`."""
import docx
import yaml
from docx.oxml.ns import qn
from lxml import etree

APP = "applications/2026-10-23_Example-Company_Working-Student-Marketing"
CV = "Lena_Fischer_CV_Example-Company.docx"


def mono_master(sample):
    """Give the first run of the master CV a second font, as a two-font design would."""
    path = sample / "cv" / "Lena_Fischer_CV.docx"
    d = docx.Document(str(path))
    run = next(r for p in d.paragraphs for r in p.runs if r.text.strip())
    run.font.name = "Courier New"
    d.save(str(path))


def set_config(sample, **values):
    path = sample / "config.yaml"
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg.update(values)
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")


def fonts_and_fallbacks(path):
    d = docx.Document(str(path))
    used = {rf.get(qn("w:ascii")) for root in (d.element, d.styles.element) for rf in root.iter(qn("w:rFonts"))}
    table = next(rel.target_part for rel in d.part.rels.values() if rel.reltype.endswith("/fontTable"))
    alts = {f.get(qn("w:name")): f.find(qn("w:altName")).get(qn("w:val"))
            for f in etree.fromstring(table.blob).iter(qn("w:font")) if f.find(qn("w:altName")) is not None}
    return used - {None}, alts


def test_default_sets_one_font(tool, sample):
    mono_master(sample)
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 0, r.stderr
    used, alts = fonts_and_fallbacks(sample / APP / CV)
    assert used == {"Arial"}
    assert alts["Arial"] == "Arial"


def test_keep_keeps_the_master_fonts(tool, sample):
    mono_master(sample)
    set_config(sample, font="keep", fallback_font={"Arial": "Helvetica", "Courier New": "Consolas"})
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode == 0, r.stderr
    used, alts = fonts_and_fallbacks(sample / APP / CV)
    assert {"Arial", "Courier New"} <= used   # plus any other font the master names (its template styles)
    assert alts["Arial"] == "Helvetica" and alts["Courier New"] == "Consolas"


def test_bad_fallback_font_fails(tool, sample):
    set_config(sample, fallback_font=["Arial"])
    r = tool("build_application.py", APP, "--no-pdf")
    assert r.returncode != 0 and "fallback_font must be a font name or a map" in r.stderr
