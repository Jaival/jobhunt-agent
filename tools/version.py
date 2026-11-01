"""The engine version: the VERSION file in engine/, plus the git commit when engine/ is a clone.

VERSION holds MAJOR.MINOR.PATCH for a release (the git tag is vMAJOR.MINOR.PATCH) and MAJOR.MINOR.PATCH-dev on
the next branch between releases; docs/RELEASING.md says when each number goes up. Like setup_check.py, this
doesn't import config.py, so it works before config.yaml exists.

Release channels (engine_channel in config.yaml): "stable" (the default) updates to the newest release tag
vX.Y.Z only; "next" follows the next branch, for the maintainer and testers. update() says what an update would
move to; setup_check.py and upgrade.py both use it.

Usage (from the workspace folder):
    python engine/tools/version.py        prints e.g. "0.3.0 (a1b2c3d)"; "a1b2c3d-dirty" when engine/ has local edits
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1]
VERSION_FILE = ENGINE / "VERSION"
CHANNELS = ("stable", "next")
RELEASE_TAG = re.compile(r"v(\d+)\.(\d+)\.(\d+)")


def version():
    """The version in VERSION, or "unknown" when the file is missing."""
    try:
        return VERSION_FILE.read_text(encoding="utf-8-sig").strip() or "unknown"  # -sig: Windows editors add a BOM
    except OSError:
        return "unknown"


def git(*args, timeout=30, engine=None):
    """Run git in engine/ (or another clone); None when git is missing, it isn't a clone, or the command fails."""
    engine = engine or ENGINE
    if not shutil.which("git") or not (engine / ".git").exists():
        return None
    try:
        r = subprocess.run(["git", "-C", str(engine), *args], capture_output=True, text=True, timeout=timeout,
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


def parse(v):
    """"1.2.3" -> (1, 2, 3, 1); "1.2.3-dev" -> (1, 2, 3, 0), so a dev version sorts below its release; None if
    it isn't a version."""
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)(-dev)?", v.strip())
    return (int(m[1]), int(m[2]), int(m[3]), 0 if m[4] else 1) if m else None


def channel(cfg):
    """engine_channel from config.yaml: "stable" when it's missing; ValueError for anything else."""
    value = str(cfg.get("engine_channel") or "stable").strip().lower()
    if value not in CHANNELS:
        raise ValueError(f"engine_channel: {cfg.get('engine_channel')!r} in config.yaml isn't stable or next")
    return value


def newest_tag(engine=None):
    """The highest release tag (vX.Y.Z, nothing after it) the clone knows, or None."""
    tags = [t for t in (git("tag", "-l", "v*", engine=engine) or "").split() if RELEASE_TAG.fullmatch(t)]
    return max(tags, key=parse, default=None)


def update(chan, engine=None):
    """What an update on this channel moves to, from what the last fetch saw: (ref, text) or None.

    stable: the newest tag, when it's a higher version than engine/VERSION. Commits on next never count, and an
    engine ahead of the newest release (a former next user) stays where it is until a release catches up.
    next: origin/next, when it has commits engine/ doesn't."""
    engine = engine or ENGINE
    if chan == "next":
        n = (git("rev-list", "--count", "HEAD..origin/next", engine=engine) or "").strip()
        return ("origin/next", f"{n} new change(s) on next") if n.isdigit() and int(n) else None
    tag = newest_tag(engine)
    try:
        have = parse((engine / "VERSION").read_text(encoding="utf-8-sig"))
    except OSError:
        have = None
    if tag and (have is None or parse(tag) > have):
        return tag, f"release {tag}"
    return None


if __name__ == "__main__":
    print(describe())
    sys.exit(0)
