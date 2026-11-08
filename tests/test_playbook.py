"""tools/playbook.py: print chosen playbook sections, and the sections the routine and the tailor print."""
import re

import permissions
import playbook
from conftest import ENGINE

DAILY, FRIDAY, TAILOR = set("ABEFG"), set("ABEFGHI"), set("BCD")


def test_all_sections_together_are_the_whole_file(capsys):
    assert playbook.main(list("ABCDEFGHI")) == 0
    assert capsys.readouterr().out == playbook.PLAYBOOK.read_text(encoding="utf-8")


def test_sections_keep_the_opening_lines_and_the_file_order(capsys):
    assert playbook.main(["f", "B"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("# Career-ops playbook") and "nothing here\nallows sending" in out
    assert out.index("## B. ") < out.index("## F. ") and "## A. " not in out and "## G. " not in out


def test_an_unknown_letter_fails(capsys):
    assert playbook.main(["A", "Z"]) == 1
    assert "no playbook section Z" in capsys.readouterr().err


def test_no_letters_lists_the_headings(capsys):
    assert playbook.main([]) == 0
    assert capsys.readouterr().out.splitlines()[0].startswith("## A. ")


def test_the_routine_prints_every_section_it_points_to():
    routine = (ENGINE / "ROUTINE.md").read_text(encoding="utf-8")
    assert "playbook.py A B E F G` (Fridays: `A B E F G H I`)" in routine
    cited = set(re.findall(r"playbook ([A-I])\b", routine))
    assert cited <= FRIDAY and cited - {"H", "I"} <= DAILY      # H and I are the Friday steps only
    assert set(playbook.sections(playbook.PLAYBOOK.read_text(encoding="utf-8"))[1]) >= FRIDAY | TAILOR


def test_the_tailor_prints_its_sections():
    tailor = (permissions.TEMPLATE.parent / "agents" / "tailor.md").read_text(encoding="utf-8")
    assert "playbook.py B C D" in tailor and "career-ops-playbook.md" not in tailor
    assert set(re.findall(r"playbook ([A-I])\b", tailor)) <= TAILOR
