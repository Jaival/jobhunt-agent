"""The workspace permission template and permissions.install (S1-1): what it denies, and merging without loss."""
import fnmatch
import json

import pytest
import yaml

import permissions

DENY = json.loads(permissions.TEMPLATE.read_text(encoding="utf-8"))["permissions"]["deny"]
TOOL_RULES = [r for r in DENY if "(" not in r]
# Connector names differ per surface: Desktop scheduled runs use the connector ID, the CLI claude_ai_<Name>, cloud
# and Cowork the bare name (docs/spike-scheduled-tasks.md).
PREFIXES = ["mcp__7d0bd227-64a7-4b4c-aede-c1c972a37d98__", "mcp__claude_ai_Gmail__", "mcp__Gmail__"]


def denied(tool):
    return any(fnmatch.fnmatchcase(tool, rule) for rule in TOOL_RULES)


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("name", ["send_message", "reply", "forward", "create_draft", "update_draft",
                                  "trash_message", "trash_thread", "mark_message_spam", "mark_thread_spam"])
def test_denies_gmail_writes_under_every_name(prefix, name):
    assert denied(prefix + name)


@pytest.mark.parametrize("tool", [
    "mcp__obscura__browser_type", "mcp__obscura__browser_fill", "mcp__obscura__browser_fill_form",
    "mcp__obscura__browser_select_option", "mcp__obscura__browser_press_key", "mcp__obscura__browser_set_cookie",
    "mcp__obscura__browser_set_storage_state", "mcp__Claude_Browser__form_input",
    "mcp__claude_ai_Upwork__upwork__send_message", "mcp__claude_ai_Google_Drive__share_file",
])
def test_denies_tools_that_send_or_type_data(tool):
    assert denied(tool)


@pytest.mark.parametrize("tool", [
    # what the daily runs call (transcripts of 18-25 Oct 2026) and what ROUTINE.md needs
    "mcp__obscura__browser_navigate", "mcp__obscura__browser_evaluate", "mcp__obscura__browser_markdown",
    "mcp__obscura__browser_links", "mcp__obscura__browser_close", "mcp__obscura__browser_forward",
    "mcp__obscura__browser_network_requests", "mcp__obscura__browser_click", "mcp__Claude_Browser__navigate",
    "mcp__Claude_Browser__get_page_text", "mcp__679f2676-80e4-4a78-88dd-ce42b5a2e410__search_jobs",
    "mcp__claude_ai_Indeed__get_job_details", "mcp__claude_ai_Gmail__search_threads",
    "mcp__claude_ai_Gmail__get_thread", "mcp__claude_ai_Gmail__untrash_message",
    "mcp__claude_ai_Gmail__get_message",
])
def test_keeps_what_the_routine_uses(tool):
    assert not denied(tool)


def test_master_files_from_config_are_read_only():
    want = permissions.wanted({"master_cv": "cv/Jonas_Becker_Lebenslauf.docx",
                               "master_letter": "./cv/Jonas_Becker_Anschreiben.docx"})
    deny = want["permissions"]["deny"]
    assert "Edit(/cv/Jonas_Becker_Lebenslauf.docx)" in deny and "Edit(/cv/Jonas_Becker_Anschreiben.docx)" in deny
    assert "Edit(/engine/**)" in deny and "Edit(/.claude/**)" in deny


def test_template_and_outside_masters_get_no_rule():
    for cfg in ({"master_cv": "cv/Your_Name_CV.docx", "master_letter": "cv/Your_Name_CoverLetter.docx"},
                {"master_cv": "C:/Users/me/CV.docx"}, {}):
        assert permissions.wanted(cfg)["permissions"]["deny"] == DENY


def test_install_merges_and_is_idempotent(tmp_path):
    (tmp_path / ".claude").mkdir()
    own = {"model": "opus", "permissions": {"allow": ["Bash(git status)"], "deny": ["mcp__*__reply"]},
           "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo done"}]}]}}
    (tmp_path / ".claude" / "settings.json").write_text(json.dumps(own), encoding="utf-8")
    added = permissions.install(tmp_path, {"master_cv": "cv/Me_CV.docx"})
    data = json.loads((tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert data["model"] == "opus" and data["hooks"]["Stop"] == own["hooks"]["Stop"]
    assert "jobhunt_guard.py" in data["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert (tmp_path / ".claude" / "hooks" / "jobhunt_guard.py").is_file()
    assert "file .claude/hooks/jobhunt_guard.py" in added
    assert data["permissions"]["allow"] == ["Bash(git status)", "Bash(python engine/tools/*)"]
    assert data["permissions"]["deny"].count("mcp__*__reply") == 1
    assert set(DENY) | {"Edit(/cv/Me_CV.docx)"} == set(data["permissions"]["deny"])
    assert "deny mcp__*__reply" not in added and "deny Edit(/cv/Me_CV.docx)" in added
    assert permissions.install(tmp_path, {"master_cv": "cv/Me_CV.docx"}) == []
    assert permissions.missing(tmp_path, {"master_cv": "cv/Me_CV.docx"}) == []


def test_hooks_are_merged_by_command():
    want = {"hooks": {"PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "python g.py"}]}]}}
    have = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "python g.py"}]}]}}
    assert permissions.merge(have, want) == (have, [])
    merged, added = permissions.merge({}, want)
    assert merged["hooks"] == want["hooks"] and added == ["hook PreToolUse python g.py"]


def test_broken_settings_are_left_alone(tmp_path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(permissions.SettingsError, match="isn't valid JSON"):
        permissions.install(tmp_path)
    assert (tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8") == "{not json"


def test_setup_check_installs_and_warns(tool, sample):
    settings = sample / ".claude" / "settings.json"
    result = json.loads(tool("setup_check.py", "--json").stdout)
    check = next(c for c in result["checks"] if c["area"] == "safety")
    assert check["status"] == "warn" and "--init" in check["fix"]
    result = json.loads(tool("setup_check.py", "--init", "--json").stdout)
    assert any("permission rule(s)" in line for line in result["init"])
    assert next(c for c in result["checks"] if c["area"] == "safety")["status"] == "ok"
    cfg = yaml.safe_load((sample / "config.yaml").read_text(encoding="utf-8"))
    deny = json.loads(settings.read_text(encoding="utf-8"))["permissions"]["deny"]
    assert f"Edit(/{cfg['master_cv']})" in deny and f"Edit(/{cfg['master_letter']})" in deny


def test_migrate_adds_rules_to_existing_settings(tool_de, sample_de):
    (sample_de / ".claude").mkdir(exist_ok=True)
    (sample_de / ".claude" / "settings.local.json").write_text('{"permissions": {"allow": ["Bash(ls)"]}}',
                                                               encoding="utf-8")
    (sample_de / ".claude" / "settings.json").write_text('{"permissions": {"allow": ["Bash(git log)"]}}',
                                                         encoding="utf-8")
    r = tool_de("upgrade.py", "migrate", "--dry-run")
    assert "permission rules: would add" in r.stdout, r.stdout + r.stderr
    assert "engine" not in (sample_de / ".claude" / "settings.json").read_text(encoding="utf-8")
    r = tool_de("upgrade.py", "migrate")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "permission rules: added" in r.stdout
    data = json.loads((sample_de / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert data["permissions"]["allow"][0] == "Bash(git log)" and "Edit(/engine/**)" in data["permissions"]["deny"]
    assert (sample_de / ".claude" / "settings.local.json").read_text(encoding="utf-8") == \
        '{"permissions": {"allow": ["Bash(ls)"]}}'
    assert "permission rules: all in place" in tool_de("upgrade.py", "migrate").stdout
