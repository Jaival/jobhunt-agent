"""Check whether the workspace is ready for the daily routine, and create the missing scaffolding.

The routine runs this first (engine/ROUTINE.md step 0). When anything is "todo", it switches to the
first-run interview in engine/ONBOARDING.md instead of searching. Unlike the other tools this one
doesn't import config.py, because config.py stops when config.yaml is missing.

Usage (from the workspace folder, the one that contains engine/):
    python engine/tools/setup_check.py            list every check: ok / todo / warn
    python engine/tools/setup_check.py --init     first copy the templates and create the folders
                                                  (never overwrites an existing file)
    python engine/tools/setup_check.py --json     same checks as JSON, for the routine

Exit code 0 = ready (warnings allowed), 1 = something is still "todo".
"""
import argparse
import importlib.util
import json
import os
import re
import shutil
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("JOBHUNT_ROOT") or ENGINE.parent)
TEMPLATES = ENGINE / "templates" / "workspace"

FOLDERS = ["applications", "daily", "data", "follow-ups", "interview-prep", "reviews", "backups", "cv", "tracker"]
PACKAGES = {"docx": "python-docx", "openpyxl": "openpyxl", "pypdf": "pypdf", "yaml": "pyyaml", "requests": "requests"}
CONFIG_KEYS = ("applicant", "file_prefix", "master_cv", "master_letter", "variants", "letter_city")
# Values that only appear in the templates; a workspace that still has them isn't filled in.
TEMPLATE_VALUES = {"applicant": "Your Name", "file_prefix": "Your_Name",
                   "master_cv": "cv/Your_Name_CV.docx", "master_letter": "cv/Your_Name_CoverLetter.docx"}
PLACEHOLDER = re.compile(r"<(?:Your Name|Name|city|Degree|university|focus|fields|role at company|internship|"
                         r"only ones[^>]*|level|20|40|ASAP|6/12|where[^>]*|tools and skills[^>]*|numbers and[^>]*|"
                         r"languages, tools[^>]*|e\.g\.[^>]*|as soon as possible|\.\.\.|role families[^>]*|"
                         r"preferences[^>]*|your [^>]*|degree|stack|url|year|one-line description|"
                         r"what it does[^>]*|anything that[^>]*|role types)>")
GITIGNORE = "# Public engine repo, cloned here\nengine/\n# Build temp files and search output\n~build_*\n~$*\ndata/candidates.json\n"


def init():
    """Copy the workspace templates and create the folders. Prints what it did."""
    done = []
    for src in sorted(TEMPLATES.rglob("*")):
        dst = ROOT / src.relative_to(TEMPLATES)
        if src.is_dir():
            continue
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            done.append(f"copied {dst.relative_to(ROOT).as_posix()}")
    for name in FOLDERS:
        if not (ROOT / name).is_dir():
            (ROOT / name).mkdir(parents=True)
            done.append(f"created {name}/")
    if not (ROOT / ".gitignore").exists():
        (ROOT / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
        done.append("wrote .gitignore (keeps engine/ out of your private repo)")
    return done


def placeholders(path):
    text = path.read_text(encoding="utf-8")
    return sorted(set(PLACEHOLDER.findall(text)))


def cv_layout(path):
    """Problems with the master CV layout that engine/tools/build_application.py needs (cv/README.txt)."""
    import docx
    doc = docx.Document(str(path))
    problems = []
    if not doc.tables:
        return ["the CV is not one Word table (header row + main/side columns)"]
    text = "\n".join(c.text for row in doc.tables[0].rows for c in row.cells)
    for heading in ("PROJECTS", "EXPERIENCE", "EDUCATION"):
        if heading not in text:
            problems.append(f"no {heading} heading")
    if "Skills" not in text:
        problems.append("no Skills heading in the side column")
    return problems


def unmatched_variants(cv_path, variants_path):
    """Ids in variants.yaml whose master text isn't found exactly once in the CV (the builder stops on these)."""
    import docx
    import yaml
    key = lambda s: re.sub(r"\s+", " ", s).strip().lower().lstrip("- ")
    table = docx.Document(str(cv_path)).tables[0]
    paras = [key(p.text) for c in (table.rows[1].cells[0], table.rows[1].cells[-1]) for p in c.paragraphs]
    variants = yaml.safe_load(variants_path.read_text(encoding="utf-8")) or {}
    return [vid for vid, v in variants.items()
            if sum(1 for p in paras if p and p.startswith(key(v.get("master") or "")[:60])) != 1]


def checks():
    """Every check as {area, item, status, fix}. Status: ok, todo (blocks the routine) or warn."""
    out = []

    def add(area, item, ok, fix="", warn=False):
        out.append({"area": area, "item": item, "status": "ok" if ok else ("warn" if warn else "todo"), "fix": fix})

    missing = [pip for mod, pip in PACKAGES.items() if importlib.util.find_spec(mod) is None]
    add("python", "packages", not missing, f"pip install {' '.join(missing)}")

    for name in FOLDERS:
        add("folders", f"{name}/", (ROOT / name).is_dir(), "python engine/tools/setup_check.py --init")

    cfg_path = ROOT / "config.yaml"
    cfg = {}
    if cfg_path.exists() and "yaml" not in missing:
        import yaml
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    add("config.yaml", "file", cfg_path.exists(), "python engine/tools/setup_check.py --init")
    if cfg_path.exists():
        for key in CONFIG_KEYS:
            value = cfg.get(key)
            add("config.yaml", key, bool(value) and value != TEMPLATE_VALUES.get(key),
                f"set {key} (onboarding asks for it)")
        home = (cfg.get("search") or {}).get("home") or {}
        add("config.yaml", "search.home", bool(home.get("wo")), "set search.home.wo to your city", warn=True)

    for key, label in (("master_cv", "master CV"), ("master_letter", "master cover letter")):
        p = ROOT / str(cfg.get(key) or "")
        present = bool(cfg.get(key)) and p.is_file()
        add("cv", label, present, f"put your {label} (.docx) at {cfg.get(key) or 'cv/'}")
        if key == "master_cv" and present and "docx" not in missing:
            problems = cv_layout(p)
            add("cv", "CV layout for the builder", not problems,
                "; ".join(problems) + " (see cv/README.txt; tailoring still works, building documents doesn't)",
                warn=True)
            var_path = ROOT / str(cfg.get("variants") or "")
            if not problems and cfg.get("variants") and var_path.is_file() and "yaml" not in missing:
                left = unmatched_variants(p, var_path)
                add("cv", "variants.yaml matches the master CV", not left,
                    f"not in your CV: {', '.join(left[:6])}; replace these entries with your own CV bullets "
                    "or delete them (onboarding does this)")

    for name, fix in (("CLAUDE.md", "fill in your profile (onboarding asks for it)"),
                      ("projects.md", "describe your projects, or delete the example ones")):
        p = ROOT / name
        if not p.exists():
            add("profile", name, False, "python engine/tools/setup_check.py --init")
            continue
        left = placeholders(p)
        add("profile", name, not left, f"{fix}; still open: {', '.join(left[:6])}")
    claude = ROOT / "CLAUDE.md"
    if claude.exists():
        add("profile", "CLAUDE.md imports engine/RULES.md",
            "@engine/RULES.md" in claude.read_text(encoding="utf-8"), "add the line @engine/RULES.md")

    for name in ("sources.md", "companies.md", "cv/variants.yaml", "tracker/Job_Application_Tracker.xlsx"):
        add("workspace", name, (ROOT / name).exists(), "python engine/tools/setup_check.py --init")

    add("documents", "Microsoft Word (PDF export)", sys.platform == "win32",
        "PDF export needs Windows with Word; the .docx files are still built", warn=True)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--init", action="store_true", help="copy templates and create folders first")
    ap.add_argument("--json", action="store_true", help="print the checks as JSON")
    args = ap.parse_args()

    done = init() if args.init else []
    result = checks()
    todo = [c for c in result if c["status"] == "todo"]
    if args.json:
        print(json.dumps({"root": str(ROOT), "ready": not todo, "init": done, "checks": result}, indent=2))
    else:
        for line in done:
            print(f"init  {line}")
        for c in result:
            mark = {"ok": "ok  ", "todo": "TODO", "warn": "warn"}[c["status"]]
            fix = f"  -> {c['fix']}" if c["status"] != "ok" and c["fix"] else ""
            print(f"{mark}  {c['area']}: {c['item']}{fix}")
        print(f"\n{'READY' if not todo else f'NOT READY: {len(todo)} item(s) to do'}  ({ROOT})")
    sys.exit(1 if todo else 0)


if __name__ == "__main__":
    main()
