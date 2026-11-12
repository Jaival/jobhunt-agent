"""Decision inbox (S4-6): the brief's Decisions checklist; decisions.py turns ticked boxes into actions for the
next run and carries unticked ones over for 7 days."""
import re

import pytest

from test_stamping import ENGINE

URL = "https://jobs.example/acme/1"
BRIEF = f"""engine 1.0.0 (a1b2c3d) · model m

## Decisions
- [x] Skip the draft 2026-10-20_Beta_Sales (10 days old) `skip 2026-10-20_Beta_Sales`
- [ ] Tailor Acme GmbH: Werkstudent Marketing (score 66) `tailor {URL}`
- [X] Mark as sent: 2026-10-30_Acme_Marketing `sent 2026-10-30_Acme_Marketing`
- [ ] Tailor Old AG: Praktikum (score 61) `tailor https://jobs.example/old` · since 2026-10-24

Done from your decisions:
- tailor https://jobs.example/x: tailored

## Apply today
- [ ] not a decision `skip nothing`
"""


def brief(sample, day, text):
    (sample / "daily").mkdir(exist_ok=True)
    (sample / "daily" / f"{day}.md").write_text(text, encoding="utf-8")


def test_ticked_boxes_become_actions_and_open_ones_carry_over(tool, sample):
    brief(sample, "2026-10-29", BRIEF.replace("[x] Skip", "[ ] Skip"))       # older: the newer brief wins
    brief(sample, "2026-10-30", BRIEF)
    brief(sample, "2026-10-31", "Setup needed: config.yaml is from an older engine version.")   # no section
    brief(sample, "2026-11-01", "## Decisions\n- [x] Mark as sent: x `sent x`\n")              # today: not read
    r = tool("decisions.py", "--today", "2026-11-01")
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines() == [
        "from daily/2026-10-30.md",
        "DO       skip 2026-10-20_Beta_Sales",
        f"KEEP     - [ ] Tailor Acme GmbH: Werkstudent Marketing (score 66) `tailor {URL}` · since 2026-10-30",
        "DO       sent 2026-10-30_Acme_Marketing",
        "EXPIRED  tailor https://jobs.example/old (open since 2026-10-24)",
    ]


def test_weekend_keeps_ticked_tailor_items_for_monday(tool, sample):
    brief(sample, "2026-10-30", BRIEF.replace("[ ] Tailor Acme", "[x] Tailor Acme"))
    out = tool("decisions.py", "--no-tailor", "--today", "2026-10-31").stdout.splitlines()
    assert f"KEEP     - [x] Tailor Acme GmbH: Werkstudent Marketing (score 66) `tailor {URL}` · since 2026-10-30" in out
    assert "DO       skip 2026-10-20_Beta_Sales" in out


def test_a_logged_action_isnt_done_twice(tool, sample):
    """A run that acted but stopped before its brief: the next run sees DONE, not DO."""
    brief(sample, "2026-10-30", BRIEF)
    r = tool("decisions.py", "done", "2026-10-30", "sent", "2026-10-30_Acme_Marketing")
    assert r.returncode == 0 and r.stdout.startswith("logged: sent")
    out = tool("decisions.py", "--today", "2026-11-01").stdout.splitlines()
    assert "DONE     sent 2026-10-30_Acme_Marketing" in out and "DO       skip 2026-10-20_Beta_Sales" in out
    brief(sample, "2026-11-01", BRIEF)                     # the same tick in a later brief is a new decision
    assert "DO       sent 2026-10-30_Acme_Marketing" in tool("decisions.py", "--today", "2026-11-02").stdout


def test_unknown_action_stops_and_no_brief_is_no_decisions(tool, sample):
    assert tool("decisions.py").stdout.startswith("no decisions")
    brief(sample, "2026-10-30", "## Decisions\n- [x] Delete it `delete 2026-10-20_Beta_Sales`\n")
    r = tool("decisions.py", "--today", "2026-11-01")
    assert r.returncode == 1 and "unknown action 'delete'" in r.stderr


def test_routine_line_forms_parse(tool, sample):
    """The three line forms ROUTINE.md step 8 asks for are the ones decisions.py reads."""
    routine = (ENGINE / "ROUTINE.md").read_text(encoding="utf-8")
    forms = re.findall(r"^  - `` (- \[ \] .*?) `` for each", routine, re.M)
    assert len(forms) == 3
    brief(sample, "2026-10-31", "## Decisions\n" + "\n".join(f.replace("[ ]", "[x]") for f in forms) + "\n")
    out = tool("decisions.py", "--today", "2026-11-01").stdout.splitlines()
    assert out[1:] == ["DO       tailor <url>", "DO       sent <folder>", "DO       skip <folder>"]
    assert "python engine/tools/decisions.py" in routine and "--no-tailor" in routine


@pytest.mark.parametrize("box, kind", [
    ("- [x ]", "DO"), ("- [ x]", "DO"), ("-[x]", "DO"), ("- [X]", "DO"), ("*  [x]", "DO"),
    ("- []", "KEEP"), ("- [  ]", "KEEP"),
])
def test_odd_checkbox_spacing(tool, sample, box, kind):
    brief(sample, "2026-10-31", f"## Decisions\n{box} Mark as sent: f `sent 2026-10-30_Acme_Marketing`\n")
    out = tool("decisions.py", "--today", "2026-11-01").stdout.splitlines()
    assert out[1].startswith(kind) and (kind == "KEEP" or out[1] == "DO       sent 2026-10-30_Acme_Marketing")
