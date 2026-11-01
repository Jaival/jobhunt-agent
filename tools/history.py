"""Workspace history: a local git repo in the workspace folder, one commit per daily run.

`setup_check.py --init` calls init(): when the workspace isn't in a git repo yet it runs `git init` and makes sure
.gitignore keeps out engine/ (the public engine clone), backups/ and Office temp files. A workspace that already
is a repo (or sits inside one) is left as it is. The routine runs `commit` at the end of each run (ROUTINE.md
step 8): it commits every change as "daily run 2026-12-14, engine v1.0.0". It never adds a remote or pushes:
the history stays on this computer. Like setup_check.py, this doesn't import config.py.

Usage (from the workspace folder):
    python engine/tools/history.py commit       commit today's changes (prints the commit, or why there is none)
"""
import argparse
import datetime as dt
import os
import shutil
import subprocess
import sys
from pathlib import Path

import version

ENGINE = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("JOBHUNT_ROOT") or ENGINE.parent)
IGNORE = ["engine/", "engine-new/", "backups/", "~$*", "~build_*", "data/candidates.json"]
# Used only when git has no user.name / user.email (a new computer): git commit refuses to run without them.
IDENTITY = ["-c", "user.name=JobHunt routine", "-c", "user.email=routine@localhost"]


def git(root, *args, check=False):
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8")
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r


def toplevel(root):
    """The repo folder that contains root, or None when root isn't in a git repo (or git is missing)."""
    if not shutil.which("git"):
        return None
    r = git(root, "rev-parse", "--show-toplevel")
    return Path(r.stdout.strip()).resolve() if r.returncode == 0 else None


def init(root=ROOT):
    """git init the workspace when it isn't in a repo yet. Returns what it did (a list of lines for setup_check)."""
    if not shutil.which("git"):
        return ["no workspace history: git isn't installed"]
    if toplevel(root):
        return []
    git(root, "init", "-q", check=True)
    path = root / ".gitignore"
    have = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    missing = [line for line in IGNORE if line not in have]
    if missing:
        text = "\n".join(have + ["# Kept out of the workspace history", *missing]) + "\n"
        path.write_text(text.lstrip("\n"), encoding="utf-8")
    return ["started the workspace history (git init; engine/ and backups/ stay out of it, nothing is pushed)"]


def commit(root=ROOT, today=None):
    """Commit every change in the workspace. Returns the line to print."""
    top = toplevel(root)
    if top is None:
        return "no history: the workspace isn't a git repo (python engine/tools/setup_check.py --init starts one)"
    if top != root.resolve():
        return f"no history: the workspace is inside another repo ({top}); not committed"
    git(root, "add", "-A", check=True)
    if git(root, "diff", "--cached", "--quiet").returncode == 0:
        return "nothing to commit"
    msg = f"daily run {today or dt.date.today():%Y-%m-%d}, engine v{version.version()}"
    who = [] if git(root, "config", "user.email").stdout.strip() else IDENTITY
    git(root, *who, "commit", "-q", "-m", msg, check=True)
    return f"committed {git(root, 'rev-parse', '--short', 'HEAD').stdout.strip()}: {msg}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["commit"])
    ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    print(commit())
    return 0


if __name__ == "__main__":
    sys.exit(main())
