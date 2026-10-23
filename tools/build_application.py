"""Build <prefix>_CV_<short>.docx, <prefix>_Cover_Letter_<short>.docx and their PDFs from an application.md.

application.md = YAML frontmatter (CV choices, letter header) + the letter body in Markdown
(one paragraph per block, blank line between paragraphs). See engine/templates/application_template.md.

The master CV and master cover letter stay the templates (CLAUDE.md rule 5): the builder only
changes the headline, reorders the items of the sections named in the CV map (cv/layout.yaml, see
cv_map.py), and swaps bullet text for approved variants from cv/variants.yaml. It fails before writing anything if a check breaks.
Every CV keeps all projects; cv.omit_projects only works together with cv.omit_approved: <date>
(the applicant's approval). After the PDF export it fails if the CV is over 2 pages or the letter over 1.

Output for ATS autofill: file names start with the applicant's name (parsers read names from file
names), document metadata carries the applicant as author and a neutral title (Word copies it into
the PDF), and every font is set to FONT with FALLBACK_FONT as the substitute named in the font table.

Usage (from the JobHunt folder):
    python engine/tools/build_application.py applications/<folder> [--no-pdf]   (a bare folder name also works)
"""
import argparse
import copy
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

import docx
import docx.text.paragraph
import yaml

import appdirs
import cv_map
from cv_map import MapError, paragraphs

from config import CFG, ROOT, path

TOOLS = Path(__file__).resolve().parent
MASTER_CV = path("master_cv")
MASTER_LETTER = path("master_letter")
VARIANTS = path("variants")
LAYOUT = str(CFG.get("layout") or "cv/layout.yaml")
CV_KEYS = {"headline", "bullets", "variants", "omit_projects", "omit_approved"}  # plus the mapped section names

STUDENT_TYPES = {"Werkstudent", "HiWi", "Internship"}
WORDS_MIN, WORDS_MAX = 250, 350
CV_MAX_PAGES, LETTER_MAX_PAGES = 2, 1
BANNED = [
    "passionate", "i am writing to express", "just following up", "just checking in",
    "touching base", "circling back", "team player", "synergy", "hit the ground running",
    "dynamic environment", "results-driven", "go-getter",
]
APPLICANT = CFG["applicant"]          # name in metadata; files start with FILE_PREFIX
FILE_PREFIX = CFG["file_prefix"]
UNIVERSITY = CFG.get("university", "")   # student letters must name it
INTERNSHIP_DURATION = str(CFG.get("internship_duration") or "")   # internship letters must state it, e.g. "12 months"
FONT = CFG.get("font", "Open Sans")                # font for CV and letter
FALLBACK_FONT = CFG.get("fallback_font", "Open Sans")  # substitute when FONT isn't installed on the reader's machine
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class BuildError(Exception):
    pass


# ---------- application.md ----------

def read_application(folder):
    path = folder / "application.md"
    if not path.exists():
        raise BuildError(f"{path} not found")
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.S)
    if not m:
        raise BuildError("application.md needs a YAML frontmatter block between --- lines")
    meta = yaml.safe_load(m.group(1)) or {}
    body = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", m.group(2))]
    body = [p for p in body if p and not p.startswith("<!--")]
    for key in ("short", "role_type", "recipient", "subject", "greeting"):
        if not meta.get(key):
            raise BuildError(f"frontmatter is missing '{key}'")
    return meta, body


# ---------- docx helpers ----------

def set_text(p, text):
    """Replace a paragraph's text, keeping the first run's formatting (or the '-' bullet run)."""
    runs = p.runs
    # A "- " bullet whose dash shares a run with the text keeps its dash; without it the
    # no_dash item rule (cv_map.py) would treat the bullet as an item start and move it.
    prefix = "- " if p.text.lstrip().startswith("-") and not text.lstrip().startswith("-") else ""
    if not runs:
        p.add_run(prefix + text)
        return
    if runs[0].text.strip() == "-" and len(runs) > 1:
        runs[1].text = " " + text
        rest = runs[2:]
    else:
        runs[0].text = prefix + text
        rest = runs[1:]
    for r in rest:
        r.text = ""


def reorder_blocks(blocks, order, names, what):
    """blocks: {name: [p elements]} in document order, contiguous. order: list of names."""
    if order is None:
        return []
    unknown = [n for n in order if n not in blocks]
    if unknown:
        raise BuildError(f"unknown {what}: {unknown}; known: {list(blocks)}")
    missing = [n for n in names if n not in order]
    final = list(order) + missing  # anything not named keeps its relative place at the end
    last = blocks[names[-1]][-1]
    anchor, parent = last.getnext(), last.getparent()
    for n in names:
        for e in blocks[n]:
            parent.remove(e)
    for n in final:
        for e in blocks[n]:
            if anchor is not None:
                anchor.addprevious(e)
            else:
                parent.append(e)
    return final


def load_layout():
    if LAYOUT.lower() == "none":
        raise BuildError("config.yaml has layout: none, so the CV isn't mapped and documents can't be built; "
                         "send the drafts by hand or say 'remap my CV'")
    try:
        return cv_map.load(ROOT / LAYOUT)
    except MapError as e:
        raise BuildError(str(e))


# ---------- CV ----------

def build_cv(meta, variants, layout, out):
    cvm = meta.get("cv") or {}
    lmap = layout.get("cv") or {}
    sections = lmap.get("sections") or {}
    unknown = [k for k in cvm if k not in CV_KEYS and k not in sections]
    if unknown:
        raise BuildError(f"unknown cv keys {unknown}; mapped sections: {list(sections)} (cv/layout.yaml)")
    d = docx.Document(MASTER_CV)
    summary = []

    if cvm.get("headline"):
        if not lmap.get("headline"):
            raise BuildError("cv.headline is set but cv/layout.yaml maps no headline")
        try:
            set_text(cv_map.find(paragraphs(d), lmap["headline"], "headline"), cvm["headline"])
        except MapError as e:
            raise BuildError(str(e))
        summary.append(f"headline: {cvm['headline']}")

    # Variants and bullet order use ids from cv/variants.yaml, located by their master text.
    by_id = {}
    paras = paragraphs(d)
    for vid, v in variants.items():
        hits = [p for p in paras if key(p.text) and key(p.text).startswith(key(v["master"])[:60])]
        if len(hits) != 1:
            raise BuildError(f"variant '{vid}': master text found {len(hits)} times in the master CV")
        by_id[vid] = hits[0]
    picks = {vid: v["default"] for vid, v in variants.items() if v.get("default")}
    for vid in cvm.get("variants") or {}:
        if vid not in variants:
            raise BuildError(f"unknown variant id '{vid}'")
    picks.update(cvm.get("variants") or {})
    for vid, pick in picks.items():
        if pick == "master":
            continue
        alt = (variants[vid].get("variants") or {}).get(pick)
        if not alt:
            raise BuildError(f"variant '{vid}' has no option '{pick}'")
        if not alt.get("approved"):
            raise BuildError(f"variant '{vid}.{pick}' is not approved yet (cv/variants.yaml)")
        set_text(by_id[vid], alt["text"])
        summary.append(f"variant {vid}: {pick}")

    for group, order in (cvm.get("bullets") or {}).items():
        ids = [vid for vid, v in variants.items() if v.get("group") == group]
        if not ids:
            raise BuildError(f"unknown bullet group '{group}'")
        blocks = {vid: [by_id[vid]._p] for vid in ids}
        ids.sort(key=lambda vid: list(by_id[vid]._p.getparent()).index(by_id[vid]._p))
        reorder_blocks(blocks, [f"{group}.{n}" for n in order], ids, f"bullet in '{group}'")
        summary.append(f"{group} bullets: {', '.join(order)}")

    # Every CV keeps all projects (CLAUDE.md rule 5); omit_projects only works with the applicant's dated approval.
    omit = cvm.get("omit_projects") or []
    if omit and "projects" not in sections:
        raise BuildError("omit_projects needs a section named 'projects' in cv/layout.yaml")
    for name, spec in sections.items():
        try:
            names, blocks = cv_map.section(d, name, spec or {})
        except MapError as e:
            raise BuildError(str(e))
        if name == "projects" and omit:
            approved = cvm.get("omit_approved") or meta.get("omit_approved")
            if not approved or not re.match(r"^\d{4}-\d{2}-\d{2}$", str(approved)):
                raise BuildError("omit_projects needs omit_approved: <YYYY-MM-DD>, set only after the applicant approved "
                                 "leaving these projects out of this CV")
            unknown = [n for n in omit if n not in blocks]
            if unknown:
                raise BuildError(f"omit_projects: unknown project: {unknown}; known: {names}")
            both = [n for n in omit if n in (cvm.get("projects") or [])]
            if both:
                raise BuildError(f"project listed in both projects and omit_projects: {both}")
            for n in omit:
                for e in blocks.pop(n):
                    e.getparent().remove(e)
                names.remove(n)
            summary.append(f"omitted projects (approved {approved}): {', '.join(omit)}")
        if cvm.get(name):
            reorder_blocks(blocks, cvm[name], names, f"{name} item")
            summary.append(f"{name}: {', '.join(cvm[name])}")

    d.save(out)
    return d, summary


def norm(s):
    return re.sub(r"\s+", " ", s).strip().lower()


def key(s):
    """Match text without the '- ' bullet prefix."""
    return norm(s).lstrip("- ")


# ---------- letter ----------

def build_letter(meta, body, layout, out):
    d = docx.Document(MASTER_LETTER)
    if not layout.get("letter"):
        raise BuildError("cv/layout.yaml maps no letter (date, recipient, subject, greeting)")
    try:
        parts = cv_map.letter_parts(d, layout["letter"])
    except MapError as e:
        raise BuildError(str(e))
    date = meta.get("date") or dt.date.today()
    if isinstance(date, str):
        date = dt.date.fromisoformat(date)
    for part, text in (("date", f"{CFG['letter_city']}, {date:%d.%m.%Y}"), ("recipient", meta["recipient"]),
                       ("subject", meta["subject"]), ("greeting", meta["greeting"])):
        if part in parts:
            set_text(parts[part], text)
    old = [p._p for p in parts["body"]]
    proto, anchor = old[0], old[-1]
    for text in body:
        new = copy.deepcopy(proto)
        anchor.addnext(new)
        anchor = new
        set_text(docx.text.paragraph.Paragraph(new, parts["body"][0]._parent), text)
    for e in old:
        e.getparent().remove(e)
    d.save(out)
    return d


# ---------- fonts and metadata ----------

def apply_fonts(d):
    """Set every explicit font (runs, styles, defaults, numbering) to FONT and name FALLBACK_FONT as its substitute."""
    parts = [d.element, d.styles.element]
    numbering = getattr(d.part, "numbering_part", None)
    try:
        if numbering is not None:
            parts.append(numbering.element)
    except Exception:
        pass
    for root in parts:
        for rf in root.iter(f"{W}rFonts"):
            for attr in ("asciiTheme", "hAnsiTheme", "cstheme", "eastAsiaTheme"):
                rf.attrib.pop(f"{W}{attr}", None)
            for attr in ("ascii", "hAnsi", "cs", "eastAsia"):
                rf.set(f"{W}{attr}", FONT)
    defaults = d.styles.element.find(f"{W}docDefaults/{W}rPrDefault/{W}rPr")
    if defaults is not None and defaults.find(f"{W}rFonts") is None:
        rf = defaults.makeelement(f"{W}rFonts", {f"{W}{a}": FONT for a in ("ascii", "hAnsi", "cs", "eastAsia")})
        defaults.insert(0, rf)
    font_table = next((rel.target_part for rel in d.part.rels.values() if rel.reltype.endswith("/fontTable")), None)
    if font_table is not None:
        from lxml import etree
        root = etree.fromstring(font_table.blob)
        entry = next((f for f in root.iter(f"{W}font") if f.get(f"{W}name") == FONT), None)
        if entry is None:  # a complete entry; a bare one made Word hang when opening the letter
            entry = etree.SubElement(root, f"{W}font", {f"{W}name": FONT})
            for tag, val in (("charset", "00"), ("family", "swiss"), ("pitch", "variable")):
                etree.SubElement(entry, f"{W}{tag}", {f"{W}val": val})
        for old in entry.findall(f"{W}altName"):
            entry.remove(old)
        alt = etree.Element(f"{W}altName", {f"{W}val": FALLBACK_FONT})
        entry.insert(0, alt)
        font_table._blob = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def set_metadata(d, kind):
    cp = d.core_properties
    cp.author = APPLICANT
    cp.last_modified_by = APPLICANT
    cp.title = f"{APPLICANT} - {kind}"
    cp.subject = cp.keywords = cp.comments = cp.category = ""


# ---------- checks ----------

def doc_text(d):
    parts = [p.text for p in d.paragraphs]
    for t in d.tables:
        for r in t.rows:
            for c in r.cells:
                parts += [p.text for p in c.paragraphs]
    return "\n".join(parts)


def check(meta, body, cv_doc, letter_doc):
    problems = []
    for name, d in (("CV", cv_doc), ("letter", letter_doc)):
        txt = doc_text(d)
        if "[" in txt or "]" in txt:
            problems.append(f"{name}: contains '[' or ']' (placeholder?)")
        low = txt.lower()
        problems += [f"{name}: banned phrase '{b}'" for b in BANNED if b in low]
    words = sum(len(p.split()) for p in body)
    if not WORDS_MIN <= words <= WORDS_MAX:
        problems.append(f"letter body has {words} words (allowed {WORDS_MIN}-{WORDS_MAX})")
    if meta["role_type"] in STUDENT_TYPES:
        letter = " ".join(body).lower()
        for need, label in (*(((UNIVERSITY.lower(), f"{UNIVERSITY} enrolment"),) if UNIVERSITY else ()), ("as soon as possible", "start 'as soon as possible'"),
                            ("hours per week", "hours per week")):
            if need not in letter:
                problems.append(f"student letter must mention {label}")
        if meta["role_type"] == "Internship" and INTERNSHIP_DURATION and INTERNSHIP_DURATION.lower() not in letter:
            problems.append(f"internship letter must mention the duration ({INTERNSHIP_DURATION})")
    return problems, words


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder")
    ap.add_argument("--no-pdf", action="store_true")
    a = ap.parse_args()
    folder = appdirs.find(a.folder) or Path(a.folder)
    if not folder.is_absolute():
        folder = ROOT / folder
    try:
        meta, body = read_application(folder)
        variants = yaml.safe_load(VARIANTS.read_text(encoding="utf-8")) or {}
        layout = load_layout()
        short = meta["short"]
        cv_out = folder / f"{FILE_PREFIX}_CV_{short}.docx"
        letter_out = folder / f"{FILE_PREFIX}_Cover_Letter_{short}.docx"
        tmp_cv, tmp_letter = folder / f"~build_CV_{short}.docx", folder / f"~build_Letter_{short}.docx"
        cv_doc, summary = build_cv(meta, variants, layout, tmp_cv)
        letter_doc = build_letter(meta, body, layout, tmp_letter)
        for d, kind, path in ((cv_doc, "CV", tmp_cv), (letter_doc, "Cover Letter", tmp_letter)):
            apply_fonts(d)
            set_metadata(d, kind)
            d.save(path)
        problems, words = check(meta, body, cv_doc, letter_doc)
        if problems:
            raise BuildError("checks failed:\n  - " + "\n  - ".join(problems))
        tmp_cv.replace(cv_out)
        tmp_letter.replace(letter_out)
    except BuildError as e:
        for f in folder.glob("~build_*.docx"):
            f.unlink()
        print(f"FAILED {folder.name}: {e}", file=sys.stderr)
        return 1
    print(f"OK {folder.name}: letter {words} words")
    for line in summary:
        print(f"  {line}")
    if not a.no_pdf:
        subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(TOOLS / "docx2pdf.ps1"),
                        str(cv_out), str(letter_out)], check=True)
        problems = check_pages(cv_out.with_suffix(".pdf"), letter_out.with_suffix(".pdf"))
        if problems:
            print(f"FAILED {folder.name}: page check:\n  - " + "\n  - ".join(problems), file=sys.stderr)
            return 1
    return 0


def check_pages(cv_pdf, letter_pdf):
    """Word's page count is the real one (LibreOffice under-counts)."""
    import pypdf
    problems = []
    for name, path, limit in (("CV", cv_pdf, CV_MAX_PAGES), ("letter", letter_pdf, LETTER_MAX_PAGES)):
        n = len(pypdf.PdfReader(str(path)).pages)
        if n > limit:
            problems.append(f"{name} has {n} pages (max {limit})")
    if any(p.startswith("CV") for p in problems):
        problems.append("Do NOT drop or shorten a project to fix this without the applicant's approval. Try a shorter "
                        "headline first (about 72 characters, one line); otherwise ask the applicant which project to leave "
                        "out (cv.omit_projects + cv.omit_approved).")
    return problems


if __name__ == "__main__":
    sys.exit(main())
