"""Every `python engine/tools/<tool>.py ...` command in the prompts must exist in that tool: the file, the
subcommand and each --flag. A renamed flag would otherwise only fail inside a scheduled run."""
import re

import pytest

from conftest import ENGINE

PROMPTS = sorted(
    [ENGINE / n for n in ("ROUTINE.md", "RULES.md", "ONBOARDING.md", "UPGRADING.md", "career-ops-playbook.md",
                          "rubric.md", "ats-checklist.md", "SETUP.md", "README.md")]
    + list((ENGINE / "templates" / "workspace").rglob("*.md")))
COMMAND = re.compile(r"python engine/tools/((?:hooks/)?\w+\.py)([^`\n]*)")
FLAG = re.compile(r"(?<![\w-])--[a-z][\w-]*")
SUBCOMMAND = re.compile(r"""add_parser\(\s*["']([\w-]+)["']""")

# Subcommands the SUBCOMMAND regex cannot see.
SUBCOMMANDS = {
    # tools/upgrade.py main(): `for name in ("status", ...): sub.add_parser(name)`, then migrate and compare.
    "upgrade.py": {"status", "prepare", "apply", "rollback", "finish", "migrate", "compare"},
}

# (prompt, line) where the command continues on the next line, so the scan sees no subcommand.
NOT_A_COMMAND = {
    # ONBOARDING.md: "... python engine/tools/cv_map.py" ends the line; "check ..." follows on the next one.
    ("ONBOARDING.md", 88),
}


def commands():
    """(prompt file, line number, tool, the rest of the command) for every tool command in the prompts."""
    for path in PROMPTS:
        for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for m in COMMAND.finditer(line):
                yield path.relative_to(ENGINE).as_posix(), no, m.group(1), m.group(2)


COMMANDS = list(commands())


def source(tool):
    return (ENGINE / "tools" / tool).read_text(encoding="utf-8")


def test_the_scan_finds_the_commands():
    assert len(COMMANDS) > 40                      # ROUTINE.md alone has dozens
    assert {c[2] for c in COMMANDS} >= {"search_jobs.py", "ledger.py", "extract.py", "hooks/guard.py"}


@pytest.mark.parametrize("where,no,tool,rest", COMMANDS, ids=lambda v: str(v)[:40])
def test_the_tool_and_its_flags_exist(where, no, tool, rest):
    assert (ENGINE / "tools" / tool).is_file(), f"{where}:{no} names tools/{tool}, which doesn't exist"
    text = source(tool)
    for flag in FLAG.findall(rest):
        if flag == "--help" and "argparse" in text:
            continue
        assert f'"{flag}"' in text or f"'{flag}'" in text, f"{where}:{no}: tools/{tool} has no {flag}"


@pytest.mark.parametrize("where,no,tool,rest", COMMANDS, ids=lambda v: str(v)[:40])
def test_the_subcommand_exists(where, no, tool, rest):
    names = SUBCOMMANDS.get(tool) or set(SUBCOMMAND.findall(source(tool)))
    if not names:
        pytest.skip("the tool has no subcommands")
    if (where, no) in NOT_A_COMMAND:
        pytest.skip("the command continues on the next line")
    word = rest.split()[0] if rest.split() else ""
    assert word in names, f"{where}:{no}: tools/{tool} has no subcommand '{word}' (it has {sorted(names)})"
