"""Build <prefix>_CV_<short>.docx, <prefix>_Cover_Letter_<short>.docx and their PDFs from an application.md.

application.md = YAML frontmatter (CV choices, letter header) + the letter body in Markdown
(one paragraph per block, blank line between paragraphs). See engine/templates/application_template.md.

The master CV and master cover letter stay the templates (CLAUDE.md rule 5): the builder only
changes the headline, reorders sections found by their heading names, and swaps bullet text for
approved variants from cv/variants.yaml. It fails before writing anything if a check breaks.
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

from config import CFG, ROOT, path

TOOLS = Path(__file__).resolve().parent
MASTER_CV = path("master_cv")
MASTER_LETTER = path("master_letter")
VARIANTS = path("variants")

STUDENT_TYPES = {"Werkstudent", "HiWi", "Internship"}
WORDS_MIN, WORDS_MAX = 250, 350
CV_MAX_PAGES, LETTER_MAX_PAGES = 2, 1
BANNED = [
    "passionate", "i am writing to express", "just following up", "just checking in",
    "touching base", "circling back", "team player", "synergy", "hit the ground running",
    "dynamic environment", "results-driven", "go-getter",
]
CV_SECTIONS = ("PROJECTS", "EXPERIENCE", "EDUCATION", "CERTIFICATIONS")
APPLICANT = CFG["applicant"]          # name in metadata; files start with FILE_PREFIX
FILE_PREFIX = CFG["file_prefix"]
UNIVERSITY = CFG.get("university", "")   # student letters must name it
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
    # abilities parser would treat the bullet as a heading and move it.
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


def split_blocks(paras, is_start, name_of):
    blocks, names = {}, []
    current = None
    for p in paras:
        if is_start(p):
            current = name_of(p)
            names.append(current)
            blocks[current] = []
        if current:
            blocks[current].append(p._p)
    return blocks, names


def section_range(paras, start_text, end_texts):
    start = next(i for i, p in enumerate(paras) if p.text.strip() == start_text)
    end = next((i for i, p in enumerate(paras) if i > start and p.text.strip() in end_texts), len(paras))
    return start, end


# ---------- CV ----------

def build_cv(meta, variants, out):
    cvm = meta.get("cv") or {}
    d = docx.Document(MASTER_CV)
    t = d.tables[0]
    head, left, right = t.rows[0].cells[0], t.rows[1].cells[0], t.rows[1].cells[1]
    summary = []

    if cvm.get("headline"):
        set_text(head.paragraphs[1], cvm["headline"])
        summary.append(f"headline: {cvm['headline']}")

    # Variants and bullet order use ids from cv/variants.yaml, located by their master text.
    by_id = {}
    for vid, v in variants.items():
        hits = [p for c in (left, right) for p in c.paragraphs
                if key(p.text) and key(p.text).startswith(key(v["master"])[:60])]
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

    # Projects: a block starts with a non-empty line after a blank line, or with a title line (no '|')
    # followed by its stack line (with '|'); name = text before the first comma.
    lp = left.paragraphs
    s, e = section_range(lp, "PROJECTS", {"EXPERIENCE"})
    proj = lp[s + 1:e]
    starts = {i for i, p in enumerate(proj) if p.text.strip() and (
        i == 0 or not proj[i - 1].text.strip()
        or ("|" not in p.text and i + 1 < len(proj) and "|" in proj[i + 1].text))}
    blocks, names = split_blocks(
        proj, lambda p: proj.index(p) in starts, lambda p: p.text.split(",")[0].strip())
    if names:  # blank spacer lines at the end of the section stay put instead of moving with the last project
        last = blocks[names[-1]]
        while len(last) > 1 and not "".join(last[-1].itertext()).strip():
            last.pop()
    # Every CV keeps all projects (CLAUDE.md rule 5); omit_projects only works with the applicant's dated approval.
    omit = cvm.get("omit_projects") or []
    if omit:
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
    if cvm.get("projects"):
        reorder_blocks(blocks, cvm["projects"], names, "project")
        summary.append(f"projects: {', '.join(cvm['projects'])}")

    # Abilities: headings are the non-empty lines that don't start with '-'.
    rp = right.paragraphs
    s, e = section_range(rp, "Skills", {"LEADERSHIP & INITIATIVE"})
    ab = rp[s + 1:e]
    blocks, names = split_blocks(
        ab, lambda p: p.text.strip() and not p.text.strip().startswith("-"), lambda p: p.text.strip())
    if cvm.get("abilities"):
        reorder_blocks(blocks, cvm["abilities"], names, "ability")
        summary.append(f"abilities: {', '.join(cvm['abilities'])}")

    # Technical Proficiency: "Name: ..." lines, each with the blank line after it.
    rp = right.paragraphs
    s = next(i for i, p in enumerate(rp) if p.text.strip() == "Technical Proficiency")
    tech = rp[s + 2:]
    blocks, names = split_blocks(
        tech, lambda p: ":" in p.text, lambda p: p.text.split(":")[0].strip())
    if cvm.get("technical"):
        reorder_blocks(blocks, cvm["technical"], names, "technical line")
        summary.append(f"technical: {', '.join(cvm['technical'])}")

    d.save(out)
    return d, summary


def norm(s):
    return re.sub(r"\s+", " ", s).strip().lower()


def key(s):
    """Match text without the '- ' bullet prefix."""
    return norm(s).lstrip("- ")


# ---------- letter ----------

def build_letter(meta, body, out):
    d = docx.Document(MASTER_LETTER)
    ps = d.paragraphs
    date = meta.get("date") or dt.date.today()
    if isinstance(date, str):
        date = dt.date.fromisoformat(date)
    set_text(ps[3], f"{CFG['letter_city']}, {date:%d.%m.%Y}")
    set_text(ps[4], meta["recipient"])
    set_text(ps[5], meta["subject"])
    set_text(ps[7], meta["greeting"])
    closing_blank = next(p for i, p in enumerate(ps) if i > 7 and not p.text.strip())
    proto = ps[8]._p
    old = [p._p for p in ps[8:] if p._p is not closing_blank._p and ps.index(p) < ps.index(closing_blank)]
    for text in body:
        new = copy.deepcopy(proto)
        closing_blank._p.addprevious(new)
        set_text(docx.text.paragraph.Paragraph(new, closing_blank._parent), text)
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
        for need, label in ((UNIVERSITY.lower(), f"{UNIVERSITY} enrolment"), ("as soon as possible", "start 'as soon as possible'"),
                            ("hours per week", "hours per week")):
            if need not in letter:
                problems.append(f"student letter must mention {label}")
        if meta["role_type"] == "Internship" and "12 months" not in letter:
            problems.append("internship letter must mention the 12-month duration")
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
        short = meta["short"]
        cv_out = folder / f"{FILE_PREFIX}_CV_{short}.docx"
        letter_out = folder / f"{FILE_PREFIX}_Cover_Letter_{short}.docx"
        tmp_cv, tmp_letter = folder / f"~build_CV_{short}.docx", folder / f"~build_Letter_{short}.docx"
        cv_doc, summary = build_cv(meta, variants, tmp_cv)
        letter_doc = build_letter(meta, body, tmp_letter)
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
