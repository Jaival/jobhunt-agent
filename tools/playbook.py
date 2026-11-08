"""Print chosen sections of career-ops-playbook.md, so a run reads only the parts it uses.

The daily run needs A, B, E, F and G every weekday and H and I on Fridays; the tailor needs B, C and D. Reading the
whole file put about 6k characters into every later call of the run for nothing
(docs/research/token-usage-2026-11-08.md). The playbook stays one file for people to read.

Usage (from the workspace folder):
    python engine/tools/playbook.py A B E F G    the opening lines, then those sections in the file's order
    python engine/tools/playbook.py              the section headings
Exit 1 when a letter names no section.
"""
import re
import sys
from pathlib import Path

PLAYBOOK = Path(__file__).resolve().parents[1] / "career-ops-playbook.md"


def sections(text):
    """(opening lines, {letter: section text}) from the playbook's `## X. Title` headings."""
    parts = re.split(r"(?m)^(?=## [A-Z]\. )", text)
    return parts[0], {p[3]: p for p in parts[1:]}


def main(args):
    intro, found = sections(PLAYBOOK.read_text(encoding="utf-8"))
    if not args:
        print("\n".join(s.splitlines()[0] for s in found.values()))
        return 0
    wanted = {a.upper() for a in args}
    unknown = sorted(wanted - set(found))
    if unknown:
        print(f"no playbook section {', '.join(unknown)}; there are {', '.join(found)}", file=sys.stderr)
        return 1
    print(intro + "".join(s for k, s in found.items() if k in wanted), end="")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
