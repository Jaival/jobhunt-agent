"""Where application folders live, and how they move between drafts, sent and archive.

Layout:
    applications/<YYYY-MM-DD_Company_Role>/            unsent drafts
    applications/_sent/<YYYY-MM-DD_Company_Role>/      sent (tracker row exists, still open; interviews too)
    applications/_archive/<YYYY-MM-DD_Company_Role>/   rejected, closed, cold or an unsent draft older than 14 days

Folder names never change, so a folder is found by its name wherever it is. Old paths stored in the
tracker (applications/<name>/...) keep working through find().
Moves use `git mv` when the folder is tracked, otherwise a plain move.
"""
import re
import shutil
import subprocess
from pathlib import Path

from config import ROOT
APPS = ROOT / "applications"
BUCKETS = {"drafts": APPS, "sent": APPS / "_sent", "archive": APPS / "_archive"}
FOLLOWUPS = ROOT / "follow-ups"

_NAME = re.compile(r"applications[/\\](?:_sent[/\\]|_archive[/\\])?([^/\\]+)")


def name_from_path(text):
    """Folder name from any stored path or folder argument (old or new layout)."""
    text = str(text or "")
    m = _NAME.search(text)
    if m:
        return m.group(1)
    p = Path(text)
    return p.name if p.name and p.name[:4].isdigit() else None


def iter_folders():
    """Yield (bucket, path) for every application folder in all three places."""
    for bucket, base in BUCKETS.items():
        if not base.exists():
            continue
        for d in sorted(base.iterdir()):
            if d.is_dir() and not d.name.startswith("_"):
                yield bucket, d


def find(name_or_path):
    """Path of a folder given its name or any (possibly stale) path; None if not found."""
    p = Path(str(name_or_path))
    if not p.is_absolute():
        p = ROOT / p
    if p.is_dir():
        return p
    name = name_from_path(name_or_path) or Path(str(name_or_path)).name
    for _, d in iter_folders():
        if d.name == name:
            return d
    return None


def bucket_of(path):
    path = Path(path)
    return {"_sent": "sent", "_archive": "archive"}.get(path.parent.name, "drafts")


def _tracked(path):
    r = subprocess.run(["git", "ls-files", "--error-unmatch", str(path.relative_to(ROOT))],
                       cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


def move(path, bucket):
    """Move a folder to 'drafts', 'sent' or 'archive'. Returns the new path (unchanged if already there)."""
    path = Path(path)
    dest_dir = BUCKETS[bucket]
    dest = dest_dir / path.name
    if path.parent == dest_dir:
        return path
    dest_dir.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        raise FileExistsError(dest)
    if _tracked(path):
        # git mv moves tracked files; untracked files in the folder (new PDFs etc.) stay behind
        subprocess.run(["git", "mv", str(path.relative_to(ROOT)), str(dest.relative_to(ROOT))],
                       cwd=ROOT, check=True, capture_output=True, text=True)
        if path.exists():
            for f in path.rglob("*"):
                if f.is_file():
                    target = dest / f.relative_to(path)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(f), str(target))
            shutil.rmtree(path, ignore_errors=True)
    else:
        shutil.move(str(path), str(dest))
    return dest


def mark(path, label, text):
    """Add or replace a '**<label>:** text' line right under the title of job.md."""
    job = Path(path) / "job.md"
    if not job.exists():
        return
    lines = job.read_text(encoding="utf-8").split("\n")
    lines = [l for l in lines if not l.startswith(f"**{label}:**")]
    at = 1 if lines and lines[0].startswith("# ") else 0
    lines[at:at] = ["", f"**{label}:** {text}"]
    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out)
    job.write_text(out, encoding="utf-8")


def company_token(name):
    parts = name.split("_")
    return parts[1] if len(parts) > 2 else None


def _words(text):
    return {w for w in re.findall(r"[a-zäöüß0-9]+", text.lower()) if len(w) > 2}


def _title(folder):
    job = Path(folder) / "job.md"
    if job.exists():
        m = re.search(r"^# (.+)$", job.read_text(encoding="utf-8", errors="replace"), re.M)
        if m:
            return m.group(1)
    return Path(folder).name


def followups_for(folder):
    """Follow-up files (follow-ups/<date>_<Company>*.md) that belong to this folder.

    Files are matched by company token. When several folders share the token (e.g. two roles at one company,
    or Acme vs Acme-Bank), each file goes to the folder whose title overlaps most
    with the file's heading, and only to folders drafted on or before the file's date.
    """
    folder = Path(folder)
    token = company_token(folder.name)
    if not token or not FOLLOWUPS.exists():
        return []
    files = [f for f in FOLLOWUPS.glob(f"*_{token}*.md")
             if f.stem[11:] == token or f.stem[11:].startswith(token + "_")]
    if not files:
        return []
    siblings = [d for _, d in iter_folders() if company_token(d.name) == token]
    mine = []
    for f in files:
        fdate = f.name[:10]
        head = (f.read_text(encoding="utf-8", errors="replace").split("\n", 1)[0])
        cands = [d for d in siblings if d.name[:10] <= fdate] or siblings
        if folder.name not in {d.name for d in cands}:
            continue
        scores = {d.name: len(_words(head) & _words(_title(d))) for d in cands}
        shared = re.search(r"\b(two|both|all)\b", head, re.I) or max(scores.values()) == 0
        if shared or scores[folder.name] == max(scores.values()):
            mine.append(f)
    return sorted(mine)
