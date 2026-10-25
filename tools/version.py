"""The engine version: the VERSION file in engine/, plus the git commit when engine/ is a clone.

VERSION holds MAJOR.MINOR.PATCH for a release (the git tag is vMAJOR.MINOR.PATCH) and MAJOR.MINOR.PATCH-dev on
the next branch between releases; docs/RELEASING.md says when each number goes up. Like setup_check.py, this
doesn't import config.py, so it works before config.yaml exists.

Usage (from the workspace folder):
    python engine/tools/version.py        prints e.g. "0.3.0 (a1b2c3d)"
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
        return VERSION_FILE.read_text(encoding="utf-8").strip() or "unknown"
    except OSError:
        return "unknown"


def commit():
    """Short commit hash of engine/, or "" when git is missing or engine/ isn't a clone."""
    if not shutil.which("git") or not (ENGINE / ".git").exists():
        return ""
    try:
        r = subprocess.run(["git", "-C", str(ENGINE), "rev-parse", "--short", "HEAD"], capture_output=True,
                           text=True, timeout=10, encoding="utf-8")
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def describe():
    """"0.3.0 (a1b2c3d)", or just "0.3.0" outside a clone."""
    c = commit()
    return f"{version()} ({c})" if c else version()


if __name__ == "__main__":
    print(describe())
    sys.exit(0)
