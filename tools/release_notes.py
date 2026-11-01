"""Check a release tag against VERSION and CHANGELOG.md, and print its release notes.

The release workflow (.github/workflows/release.yml) runs this when a tag vX.Y.Z is pushed; docs/RELEASING.md
step 7. It fails, with the reason, when the tag isn't vX.Y.Z, VERSION on the tagged commit isn't X.Y.Z, or
CHANGELOG.md has no non-empty "## [X.Y.Z] - YYYY-MM-DD: <title>" section.

Usage (from the engine folder):
    python tools/release_notes.py v1.0.0                  print the notes (the section without its heading)
    python tools/release_notes.py v1.0.0 --out notes.md   write them to notes.md and print the release title
"""
import argparse
import re
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1]


class ReleaseError(Exception):
    pass


def notes(tag, engine=ENGINE):
    """(title, body) for the release `tag`; ReleaseError when the tag, VERSION or CHANGELOG don't agree."""
    m = re.fullmatch(r"v(\d+\.\d+\.\d+)", tag)
    if not m:
        raise ReleaseError(f"tag {tag} isn't vX.Y.Z")
    v = m[1]
    have = (engine / "VERSION").read_text(encoding="utf-8-sig").strip()
    if have != v:
        raise ReleaseError(f"VERSION is {have}, the tag says {v}: tag the release commit on main")
    text = (engine / "CHANGELOG.md").read_text(encoding="utf-8")
    head = re.search(rf"^## \[{re.escape(v)}\] - \d{{4}}-\d{{2}}-\d{{2}}: (.+)$", text, re.M)
    if not head:
        raise ReleaseError(f"CHANGELOG.md has no '## [{v}] - YYYY-MM-DD: <title>' heading")
    end = re.compile(r"^## |^\[[^\]]+\]: ", re.M).search(text, head.end())
    body = text[head.end():end.start() if end else len(text)].strip()
    if not body:
        raise ReleaseError(f"the CHANGELOG section for {v} is empty")
    return f"{tag}: {head[1].strip()}", body + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tag")
    ap.add_argument("--out", type=Path, help="write the notes here and print the title")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        title, body = notes(a.tag)
    except ReleaseError as e:
        print(f"STOPPED: {e}", file=sys.stderr)
        return 1
    if a.out:
        a.out.write_text(body, encoding="utf-8")
        print(title)
    else:
        print(body, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
