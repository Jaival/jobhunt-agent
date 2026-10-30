"""The tailor subagent (S3-2): one fresh context per job, with only the tools tailoring needs."""
import re

import yaml

import permissions

AGENT = permissions.TEMPLATE.parent / "agents" / "tailor.md"
ROUTINE = permissions.TEMPLATE.parents[3] / "ROUTINE.md"


def front():
    return yaml.safe_load(AGENT.read_text(encoding="utf-8").split("---\n", 2)[1])


def test_tools_are_an_allow_list_without_web_mail_or_agents():
    tools = {t.strip() for t in front()["tools"].split(",")}
    assert tools == {"Read", "Write", "Edit", "Glob", "Grep", "Bash"}   # no WebFetch, browser, Gmail or Agent
    assert front()["name"] == "tailor" and not front().get("omitClaudeMd")   # it needs the candidate's CLAUDE.md


def test_reply_block_matches_the_routine():
    keys = re.findall(r"^(\w+):", AGENT.read_text(encoding="utf-8").split("## What you return")[1], re.M)
    assert keys == ["folder", "build", "pdfs", "personalise", "grounding", "actions"]
    routine = ROUTINE.read_text(encoding="utf-8")
    assert "subagent_type `tailor`" in routine
    assert all(f"`{k}`" in routine for k in keys)


def test_install_copies_the_agent(tmp_path):
    added = permissions.install(tmp_path, {})
    assert "file .claude/agents/tailor.md" in added
    assert (tmp_path / ".claude" / "agents" / "tailor.md").read_text(encoding="utf-8") == AGENT.read_text(
        encoding="utf-8")
