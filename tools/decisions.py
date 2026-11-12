"""Decision inbox: the "Decisions" checklist at the top of the daily brief.

Each brief (ROUTINE.md step 8) starts with a checklist of choices only the candidate can make. Each line ends
with its action in backticks, and may say since when it has been open:

    ## Decisions
    - [ ] Tailor Acme GmbH: Werkstudent Marketing (score 66) `tailor https://jobs.example/acme/1` · since 2026-10-28
    - [ ] Mark as sent: 2026-10-30_Acme_Marketing `sent 2026-10-30_Acme_Marketing`
    - [ ] Skip the draft 2026-10-20_Beta_Sales (12 days old) `skip 2026-10-20_Beta_Sales`

The candidate ticks a box ([x]) in the file. The next run reads the newest earlier brief that has a Decisions
section and prints one line per item:

    DO       <action> <target>   ticked: act through the same tools (ROUTINE.md step 1 says which)
    DONE     <action> <target>   ticked and already acted on (in the log below): don't act again
    KEEP     <the line>          not ticked, open for less than 7 days: copy it unchanged into today's brief
    EXPIRED  <action> <target>   not ticked for 7 days: drop it (the brief's Details list it once)

Actions: `tailor <url>` (tailor the job), `sent <folder>` (the candidate sent it: tracker row, folder to
_sent/), `skip <folder>` (archive the draft). A line with another action stops the tool with the reason.
With --no-tailor (weekend runs, which don't tailor) a ticked `tailor` comes back as a ticked KEEP line, so
Monday's run acts on it.

After each action the routine runs `done`, which adds "<brief date> <action> <target>" to data/decisions_done.txt.
A ticked item already in that log comes back as DONE (list it, don't act again), so a run that stopped before it
wrote the brief doesn't add a second tracker row the next time.

Usage (from the JobHunt folder):
    python engine/tools/decisions.py [--no-tailor]
    python engine/tools/decisions.py done <brief date> <action> <target>
"""
import argparse
import datetime as dt
import re
import sys

from config import ROOT

DAILY = ROOT / "daily"
LOG = ROOT / "data" / "decisions_done.txt"
CARRY_DAYS = 7
ACTIONS = ("tailor", "sent", "skip")
HEAD = re.compile(r"^#+\s+Decisions\s*$", re.M)
ITEM = re.compile(r"^\s*[-*]\s*\[\s*([xX]?)\s*\]\s*.*`(\w+) ([^`\s]+)`.*$")
SINCE = re.compile(r"since (\d{4}-\d{2}-\d{2})")


class DecisionError(Exception):
    pass


def section(text):
    """The lines of the brief's Decisions section, or None when it has none."""
    head = HEAD.search(text)
    if not head:
        return None
    end = re.compile(r"^#|^<details", re.M).search(text, head.end())
    return text[head.end():end.start() if end else len(text)].splitlines()


def newest(today, daily=DAILY):
    """(date, lines) of the newest brief before today with a Decisions section, or None."""
    for f in sorted(daily.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].md"), reverse=True):
        day = dt.date.fromisoformat(f.stem)
        if day < today and (lines := section(f.read_text(encoding="utf-8"))) is not None:
            return day, lines
    return None


def items(day, lines):
    """(ticked, action, target, since, line) for each checklist line; DecisionError on an unknown action."""
    out = []
    for line in lines:
        m = ITEM.match(line)
        if not m:
            continue
        if m[2] not in ACTIONS:
            raise DecisionError(f"unknown action '{m[2]}' in: {line.strip()} (use {', '.join(ACTIONS)})")
        since = SINCE.search(line)
        out.append((bool(m[1]), m[2], m[3], dt.date.fromisoformat(since[1]) if since else day, line.strip()))
    return out


def plan(today, no_tailor=False, daily=DAILY, log=LOG):
    """(brief date, [(kind, text)]) with kind DO, DONE, KEEP or EXPIRED; (None, []) when no brief has decisions."""
    found = newest(today, daily)
    if not found:
        return None, []
    day, lines = found
    done = set(log.read_text(encoding="utf-8").splitlines()) if log.exists() else set()
    out = []
    for ticked, action, target, since, line in items(day, lines):
        if not SINCE.search(line):
            line += f" · since {since:%Y-%m-%d}"
        if ticked and f"{day:%Y-%m-%d} {action} {target}" in done:
            out.append(("DONE", f"{action} {target}"))
        elif ticked and not (no_tailor and action == "tailor"):
            out.append(("DO", f"{action} {target}"))
        elif ticked or (today - since).days < CARRY_DAYS:
            out.append(("KEEP", line))
        else:
            out.append(("EXPIRED", f"{action} {target} (open since {since:%Y-%m-%d})"))
    return day, out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1:2] == ["done"]:
        ap = argparse.ArgumentParser(prog="decisions.py done", description="log a decision as acted on")
        ap.add_argument("day", type=dt.date.fromisoformat)
        ap.add_argument("action", choices=ACTIONS)
        ap.add_argument("target")
        d = ap.parse_args(sys.argv[2:])
        LOG.parent.mkdir(exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(f"{d.day:%Y-%m-%d} {d.action} {d.target}\n")
        print(f"logged: {d.action} {d.target} (from the {d.day:%Y-%m-%d} brief)")
        return 0
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-tailor", action="store_true", help="weekend run: keep ticked tailor items for Monday")
    ap.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today(), help=argparse.SUPPRESS)
    a = ap.parse_args()
    try:
        day, out = plan(a.today, a.no_tailor)
    except DecisionError as e:
        print(f"STOPPED: {e}", file=sys.stderr)
        return 1
    if day is None:
        print("no decisions: no earlier brief has a Decisions section")
        return 0
    print(f"from daily/{day:%Y-%m-%d}.md")
    for kind, text in out:
        print(f"{kind:<8} {text}")
    if not out:
        print("no decisions: the section is empty")
    return 0


if __name__ == "__main__":
    sys.exit(main())
