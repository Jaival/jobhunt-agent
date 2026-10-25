"""The engine version: the VERSION file in engine/, plus the git commit when engine/ is a clone.

VERSION holds MAJOR.MINOR.PATCH for a release (the git tag is vMAJOR.MINOR.PATCH) and MAJOR.MINOR.PATCH-dev on
the next branch between releases; docs/RELEASING.md says when each number goes up. Like setup_check.py, this
doesn't import config.py, so it works before config.yaml exists.

Usage (from the workspace folder):
    python engine/tools/version.py        prints e.g. "0.3.0 (a1b2c3d)"; "a1b2c3d-dirty" when engine/ has local edits
"""
import shutil
import subprocess
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1]
VERSION_FILE = ENGINE / "VERSION"


def version():
    """The version in VERSION, or "unknown" when the file is missing."""
    try:
        return VERSION_FILE.read_text(encoding="utf-8-sig").strip() or "unknown"  # -sig: Windows editors add a BOM
    except OSError:
        return "unknown"


def git(*args, timeout=30):
    """Run git in engine/; None when git is missing, engine/ isn't a clone, or the command fails."""
    if not shutil.which("git") or not (ENGINE / ".git").exists():
        return None
    try:
        r = subprocess.run(["git", "-C", str(ENGINE), *args], capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8")
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def commit():
    """Short commit hash of engine/, with "-dirty" when engine/ has local edits; "" outside a clone."""
    c = (git("rev-parse", "--short", "HEAD", timeout=10) or "").strip()
    if c and (git("status", "--porcelain", timeout=10) or "").strip():
        c += "-dirty"
    return c


def describe():
    """"0.3.0 (a1b2c3d)", or just "0.3.0" outside a clone."""
    c = commit()
    return f"{version()} ({c})" if c else version()


if __name__ == "__main__":
    print(describe())
    sys.exit(0)
