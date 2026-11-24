"""Match a job ad's key terms (the `keywords` of its extract, ad.json) against the CV, the letter and the
candidate's own files, and keep the candidate's answers about skills in skills.md.

check: one row per term with its status, and the ATS match (the share of the ad's terms, weighted by importance,
that the CV shows):
    cv        in the built CV (before the build: in the master CV or the headline in application.md)
    letter    only in the letter
    addable   not in the CV, but in the candidate's files (CLAUDE.md without its Gaps section, projects.md,
              approved variants, skills.md rows marked yes): the headline, the letter or a variant can show it
    learning  skills.md says the candidate is learning it: the letter may name it only as something to learn
    no        skills.md or CLAUDE.md's Gaps section says the candidate doesn't have it
    confirm   in none of the files: ask the candidate (`ask`, the brief)
Matching ignores case, treats spaces and hyphens alike, matches whole terms only ("Java" is not in
"JavaScript"), and uses the aliases in engine/templates/keyword_aliases.yaml and the Aliases column of skills.md.

fact: add or update one skills.md row. `yes` needs a note saying where the candidate used it.
ask: the `confirm` terms of the drafts from the last N days, most asked first (max 5), for the brief.

Usage (from the workspace folder):
    python engine/tools/keywords.py check applications/<folder> [--json]
    python engine/tools/keywords.py fact "<skill>" yes|learning|no [--note "<where>"] [--alias "<a>, <b>"]
    python engine/tools/keywords.py ask [--days 14] [--max 5]
"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

import yaml

from config import CFG, ROOT

ENGINE = Path(__file__).resolve().parents[1]
ALIASES_FILE = ENGINE / "templates" / "keyword_aliases.yaml"
SKILLS = ROOT / "skills.md"
SKILLS_TEMPLATE = ENGINE / "templates" / "workspace" / "skills.md"
STATUSES = ("yes", "learning", "no")
WEIGHTS = {"critical": 3, "high": 2, "meaningful": 1, "preferred": 0.5}
ORDER = ("cv", "letter", "addable", "learning", "no", "confirm")
GAPS = re.compile(r"## .*(gap|never claim|lücke)", re.I)


class KeywordError(Exception):
    pass


# ---------- skills.md ----------

def skill_rows(path=SKILLS):
    """The rows of skills.md as dicts (skill, status, note, aliases); [] when there is no file."""
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.lstrip().startswith("|") else []
        if len(cells) < 2 or cells[0].lower() == "skill" or set(cells[0]) <= set("-: "):
            continue
        status = cells[1].lower()
        if status not in STATUSES:
            continue
        rows.append({"skill": cells[0], "status": status, "note": cells[2] if len(cells) > 2 else "",
                     "aliases": [a.strip() for a in (cells[3] if len(cells) > 3 else "").split(",") if a.strip()]})
    return rows


def confirmed_text(path=SKILLS):
    """The skills.md rows marked yes, as text the builder's grounding check counts as the candidate's own."""
    return "\n".join(f"{r['skill']} ({', '.join(r['aliases'])}): {r['note']}" if r["aliases"]
                     else f"{r['skill']}: {r['note']}" for r in skill_rows(path) if r["status"] == "yes")


def write_fact(skill, status, note="", aliases=(), path=SKILLS):
    """Add or update one row of skills.md (matched by skill, any case). Returns the row line."""
    import atomic
    skill, note = skill.strip(), note.strip()
    aliases = [a.strip() for a in aliases if a.strip()]
    for value in [skill, note, *aliases]:
        if "|" in value or "\n" in value or "\r" in value:
            raise KeywordError(f"no '|' or line break in a skill, note or alias: {value!r}")
    if not skill or len(skill) > 40:
        raise KeywordError("the skill must be 1-40 characters")
    if status not in STATUSES:
        raise KeywordError(f"status must be one of {', '.join(STATUSES)}")
    if status == "yes" and not note:
        raise KeywordError("a 'yes' needs --note saying where you used it (job, project, course)")
    text = path.read_text(encoding="utf-8") if path.exists() else SKILLS_TEMPLATE.read_text(encoding="utf-8")
    line = f"| {skill} | {status} | {note} | {', '.join(aliases)} |"
    lines = text.splitlines()
    for i, old in enumerate(lines):
        cells = [c.strip() for c in old.strip().strip("|").split("|")] if old.lstrip().startswith("|") else []
        if cells and cells[0].casefold() == skill.casefold() and len(cells) > 1 and cells[1].lower() in STATUSES:
            if not aliases and len(cells) > 3:  # keep the aliases the row had
                line = f"| {skill} | {status} | {note} | {cells[3]} |"
            lines[i] = line
            break
    else:
        lines.append(line)
    atomic.write_text(path, "\n".join(lines) + "\n")
    return line


# ---------- matching ----------

def pattern(term):
    """A whole-term, case-insensitive regex; spaces and hyphens match each other."""
    parts = [re.escape(p) for p in re.split(r"[\s-]+", term.strip()) if p]
    return re.compile(r"(?<!\w)" + r"[\s-]+".join(parts) + r"(?!\w)", re.I)


def alias_groups(rows):
    groups = [[str(x) for x in g] for g in yaml.safe_load(ALIASES_FILE.read_text(encoding="utf-8")) or []]
    return groups + [[r["skill"], *r["aliases"]] for r in rows if r["aliases"]]


def spellings(term, groups):
    """The term and every alias of it."""
    out = {term}
    for g in groups:
        if any(pattern(x).fullmatch(term.strip()) for x in g):
            out.update(g)
    return out


def found(term, text, groups):
    return any(pattern(s).search(text) for s in spellings(term, groups))


# ---------- the texts ----------

def read_application(folder):
    """(headline, letter body) from application.md; ("", "") when there is none yet."""
    app = folder / "application.md"
    if not app.exists():
        return "", ""
    text = app.read_text(encoding="utf-8")
    m = re.match(r"---\s*\n(.*?)\n---\s*\n?(.*)", text, re.S)
    if not m:
        return "", text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    headline = (meta.get("cv") or {}).get("headline") if isinstance(meta, dict) else ""
    return str(headline or ""), re.sub(r"<!--.*?-->", " ", m.group(2), flags=re.S)


def docx_text(path):
    import docx
    from build_application import all_text
    return all_text(docx.Document(str(path)))


def built_cv(folder):
    prefix = str(CFG.get("file_prefix") or "")
    return next(iter(sorted(folder.glob(f"{prefix}_CV_*.docx"))), None)


def own_files():
    """(own, gaps): the candidate's files as text, and CLAUDE.md's Gaps section."""
    parts, gaps = [], ""
    claude = ROOT / "CLAUDE.md"
    if claude.exists():
        for s in re.split(r"^(?=## )", claude.read_text(encoding="utf-8"), flags=re.M):
            if GAPS.match(s):
                gaps += s
            else:
                parts.append(s)
    projects = ROOT / "projects.md"
    if projects.exists():
        parts.append(projects.read_text(encoding="utf-8"))
    variants_file = ROOT / str(CFG.get("variants") or "cv/variants.yaml")
    if variants_file.exists():
        variants = yaml.safe_load(variants_file.read_text(encoding="utf-8")) or {}
        for v in variants.values() if isinstance(variants, dict) else []:
            if isinstance(v, dict):
                parts.append(str(v.get("master", "")))
                parts += [str(a.get("text", "")) for a in (v.get("variants") or {}).values()
                          if isinstance(a, dict) and a.get("approved")]
    parts.append(confirmed_text())
    return "\n".join(parts), gaps


# ---------- check ----------

def check(folder):
    """{"terms": [{term, importance, where, status}], "match": %, "top": (in CV, all) for critical/high,
    "cv_source": "built CV" | "master CV"}; None when ad.json has no keywords."""
    ad = json.loads((folder / "ad.json").read_text(encoding="utf-8"))
    terms = ad.get("keywords") or []
    if not terms:
        return None
    rows = skill_rows()
    groups = alias_groups(rows)
    cv_file = built_cv(folder)
    headline, letter = read_application(folder)
    if cv_file:
        cv, cv_source = docx_text(cv_file), "built CV"
    else:
        master = ROOT / str(CFG.get("master_cv") or "")
        cv, cv_source = (docx_text(master) if master.is_file() else "") + "\n" + headline, "master CV"
    own, gaps = own_files()
    answers = {r["skill"].casefold(): r["status"] for r in rows}
    out = []
    for k in terms:
        term = k["term"]
        said = next((answers[s.casefold()] for s in spellings(term, groups) if s.casefold() in answers), None)
        if found(term, cv, groups):
            status = "cv"
        elif said == "no" or (said is None and found(term, gaps, groups) and not found(term, own, groups)):
            status = "no"
        elif said == "learning":
            status = "learning"
        elif found(term, letter, groups):
            status = "letter"
        elif found(term, own, groups):
            status = "addable"
        else:
            status = "confirm"
        out.append({**k, "status": status})
    total = sum(WEIGHTS[t["importance"]] for t in out)
    shown = sum(WEIGHTS[t["importance"]] for t in out if t["status"] == "cv")
    top = [t for t in out if t["importance"] in ("critical", "high")]
    return {"terms": out, "match": round(100 * shown / total) if total else 0,
            "top": (sum(t["status"] == "cv" for t in top), len(top)), "cv_source": cv_source}


def summary(result):
    confirm = [t["term"] for t in result["terms"] if t["status"] == "confirm"]
    return (f"ATS match {result['match']}%, critical/high in CV {result['top'][0]}/{result['top'][1]}; "
            f"confirm: {', '.join(confirm) or '-'}")


def cmd_check(a):
    import appdirs
    folder = appdirs.find(a.folder)
    if not folder or not (folder / "ad.json").exists():
        print(f"FAILED  no application folder with an ad.json: {a.folder}", file=sys.stderr)
        return 1
    result = check(folder)
    if result is None:
        print("no keywords in this extract (read before the ad reader listed them): nothing to match")
        return 0
    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
        return 0
    print(f"Keywords from ad.json, matched against the {result['cv_source']}:\n")
    print("| Term | Importance | In the ad | Status |\n|---|---|---|---|")
    for t in sorted(result["terms"], key=lambda t: (ORDER.index(t["status"]), -WEIGHTS[t["importance"]])):
        print(f"| {t['term']} | {t['importance']} | {t['where']} | {t['status']} |")
    print(f"\n{summary(result)}")
    return 0


def cmd_fact(a):
    try:
        print(write_fact(a.skill, a.status, a.note or "", (a.alias or "").split(",")))
    except KeywordError as e:
        print(f"FAILED  {e}", file=sys.stderr)
        return 1
    return 0


def cmd_ask(a):
    import appdirs
    since = (dt.date.today() - dt.timedelta(days=a.days)).isoformat()
    asked = {}
    for bucket, folder in appdirs.iter_folders():
        if bucket != "drafts" or folder.name[:10] < since or not (folder / "ad.json").exists():
            continue
        result = check(folder)
        company = json.loads((folder / "ad.json").read_text(encoding="utf-8")).get("company") or folder.name
        for t in (result or {}).get("terms", []):
            if t["status"] == "confirm":
                entry = asked.setdefault(t["term"].casefold(), {"term": t["term"], "companies": [], "weight": 0})
                if company not in entry["companies"]:
                    entry["companies"].append(company)
                entry["weight"] += WEIGHTS[t["importance"]]
    top = sorted(asked.values(), key=lambda e: (-len(e["companies"]), -e["weight"], e["term"].casefold()))[:a.max]
    for e in top:
        print(f"ASK     {e['term']} | asked by {', '.join(e['companies'])}")
    print(f"{len(top)} skill question(s)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="match the ad's keywords against the CV, letter and your files")
    c.add_argument("folder")
    c.add_argument("--json", action="store_true")
    f = sub.add_parser("fact", help="add or update one skills.md row")
    f.add_argument("skill")
    f.add_argument("status", choices=STATUSES)
    f.add_argument("--note", help="where you used it (required for yes)")
    f.add_argument("--alias", help="other spellings, comma-separated")
    k = sub.add_parser("ask", help="the unknown terms of recent drafts, for the brief")
    k.add_argument("--days", type=int, default=14)
    k.add_argument("--max", type=int, default=5)
    a = ap.parse_args(argv)
    return {"check": cmd_check, "fact": cmd_fact, "ask": cmd_ask}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
