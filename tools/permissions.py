"""Install the workspace permission rules (engine/templates/workspace/.claude/settings.json) into a workspace.

The daily run is unattended, so what it may do is limited by Claude Code permission rules, not by instructions
alone: deny rules hold in every permission mode, auto and bypass included (docs/spike-scheduled-tasks.md). The
template denies the tools that send or type data (Gmail send/reply/draft, browser form filling) and edits of
engine/ and .claude/. On top of it, the master CV and letter named in config.yaml are made read-only (when
they are inside the workspace).

The rules only apply to a local Claude Code session whose project folder is the workspace (a Code-tab scheduled
task with "Only on this computer"); cloud and Cowork tasks ignore .claude/.

install() merges, never overwrites: rules and hooks already in .claude/settings.json stay, missing ones are added.
The one exception is a deny rule for a tool the engine needs (NEEDED: the ad-reader subagent runs through Agent):
it is removed, after a copy of the file is saved as .claude/settings.json.bak-<date>.
The other template files (.claude/hooks/jobhunt_guard.py, which starts engine/tools/hooks/guard.py) belong to the
engine and are copied when missing or changed. setup_check.py --init and upgrade.py migrate call it;
setup_check.py warns while something is missing.
"""
import copy
import datetime as dt
import json
import shutil
from pathlib import Path

import atomic

TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "workspace" / ".claude" / "settings.json"
FILES = [p for p in sorted(TEMPLATE.parent.rglob("*")) if p.is_file() and p != TEMPLATE and "__pycache__" not in p.parts]
# config.yaml values that only appear in the template: no real master file to protect yet.
TEMPLATE_MASTERS = {"cv/Your_Name_CV.docx", "cv/Your_Name_CoverLetter.docx"}
NEEDED = {"Agent"}  # tools the routine can't run without; a deny rule for them ("Agent", "Agent(...)") is removed


class SettingsError(Exception):
    pass


def settings_path(root):
    return Path(root) / ".claude" / "settings.json"


def wanted(cfg=None):
    """The template plus a deny rule for each real master file in config.yaml."""
    want = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    for key in ("master_cv", "master_letter"):
        path = str((cfg or {}).get(key) or "").replace("\\", "/").removeprefix("./")
        if path and path not in TEMPLATE_MASTERS and not Path(path).is_absolute() and ":" not in path:
            want["permissions"]["deny"].append(f"Edit(/{path})")  # /x = x in the workspace folder
    return want


def load(root):
    p = settings_path(root)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError as e:
        raise SettingsError(f"{p} isn't valid JSON ({e}); fix it by hand, then run setup_check.py --init") from e
    if not isinstance(data, dict):
        raise SettingsError(f"{p} isn't a JSON object; fix it by hand, then run setup_check.py --init")
    return data


def merge(have, want):
    """have with everything from want added and deny rules for NEEDED tools removed. Returns (merged, added) where
    added describes each change."""
    out, added = copy.deepcopy(have), []
    deny = out.get("permissions", {}).get("deny", [])
    for rule in [r for r in deny if r.split("(")[0] in NEEDED]:
        deny.remove(rule)
        added.append(f"removed deny {rule}")
    for kind, rules in want.get("permissions", {}).items():
        cur = out.setdefault("permissions", {}).setdefault(kind, [])
        for rule in rules:
            if rule not in cur:
                cur.append(rule)
                added.append(f"{kind} {rule}")
    for event, groups in want.get("hooks", {}).items():
        cur = out.setdefault("hooks", {}).setdefault(event, [])
        commands = {h.get("command") for g in cur for h in g.get("hooks", [])}
        for group in groups:
            new = [h for h in group.get("hooks", []) if h.get("command") not in commands]
            if new:
                cur.append({**group, "hooks": new})
                added += [f"hook {event} {h.get('command')}" for h in new]
    return out, added


def stale_files(root):
    """Template files that the workspace's .claude/ lacks or has in another version."""
    out = []
    for src in FILES:
        dst = Path(root) / ".claude" / src.relative_to(TEMPLATE.parent)
        if not dst.is_file() or dst.read_text(encoding="utf-8") != src.read_text(encoding="utf-8"):
            out.append(src)
    return out


def file_label(src):
    return f"file .claude/{src.relative_to(TEMPLATE.parent).as_posix()}"


def missing(root, cfg=None):
    """What install() would add (empty when the workspace has everything). Raises SettingsError."""
    return merge(load(root), wanted(cfg))[1] + [file_label(src) for src in stale_files(root)]


def install(root, cfg=None, dry_run=False):
    """Add the missing rules to <root>/.claude/settings.json, remove deny rules for NEEDED tools (backup first) and
    copy the hook files. Returns what was added or removed.
    Raises SettingsError."""
    merged, added = merge(load(root), wanted(cfg))
    files = stale_files(root)
    if not dry_run:
        backup = settings_path(root).with_name(f"settings.json.bak-{dt.date.today().isoformat()}")
        if any(a.startswith("removed ") for a in added) and not backup.exists():
            shutil.copy2(settings_path(root), backup)
        for src in files:  # the launcher first, so the hook entry never points at a missing file
            atomic.write_text(Path(root) / ".claude" / src.relative_to(TEMPLATE.parent),
                              src.read_text(encoding="utf-8"))
        if added:
            atomic.write_text(settings_path(root), json.dumps(merged, indent=2, ensure_ascii=False) + "\n")
    return added + [file_label(src) for src in files]
