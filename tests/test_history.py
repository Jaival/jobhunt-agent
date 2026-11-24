"""Workspace history (S4-4): setup_check.py --init starts a local git repo unless there is one; history.py commit
records each daily run. Nothing is ever pushed."""
import datetime as dt
import json
import subprocess

import history
from test_stamping import ENGINE


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8").stdout


def test_init_starts_the_history_once(tool, sample):
    init = json.loads(tool("setup_check.py", "--init", "--json").stdout)["init"]
    assert any(line.startswith("started the workspace history") for line in init)
    assert (sample / ".git").is_dir()
    ignore = (sample / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert {"engine/", "backups/", "~$*"} <= set(ignore)
    again = json.loads(tool("setup_check.py", "--init", "--json").stdout)["init"]
    assert not any("history" in line for line in again)


def test_commit_records_the_run_and_never_pushes(tool, sample):
    tool("setup_check.py", "--init")
    for name in ("engine/x.txt", "backups/2026-11-01/x.txt", "daily/2026-11-01.md", "cv/~$Draft.docx"):
        (sample / name).parent.mkdir(parents=True, exist_ok=True)
        (sample / name).write_text("x", encoding="utf-8")
    r = tool("history.py", "commit")
    assert r.returncode == 0, r.stderr
    v = (ENGINE / "VERSION").read_text(encoding="utf-8-sig").strip()
    assert r.stdout.strip().endswith(f": daily run {dt.date.today():%Y-%m-%d}, engine v{v}")
    files = git(sample, "ls-files").splitlines()
    assert "daily/2026-11-01.md" in files and "config.yaml" in files
    assert not [f for f in files if f.startswith(("engine/", "backups/")) or "~$" in f]
    assert tool("history.py", "commit").stdout.strip() == "nothing to commit"
    assert git(sample, "remote") == ""


def test_an_existing_repo_is_left_as_it_is(tool, sample):
    git(sample, "init", "-q")
    (sample / ".gitignore").write_text("mine/\n", encoding="utf-8")
    init = json.loads(tool("setup_check.py", "--init", "--json").stdout)["init"]
    assert not any("history" in line for line in init)
    assert (sample / ".gitignore").read_text(encoding="utf-8") == "mine/\n"


def test_a_repo_the_user_already_had_gets_the_ignore_lines_in_info_exclude(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    (ws / "engine").mkdir(parents=True)
    (ws / "backups" / "2026-01-01").mkdir(parents=True)
    (ws / "data").mkdir()
    history.git(ws, "init", "-q")                      # the user's own repo, with their own .gitignore
    (ws / ".gitignore").write_text("*.tmp\n", encoding="utf-8")
    (ws / "engine" / "x.py").write_text("x", encoding="utf-8")
    (ws / "backups" / "2026-01-01" / "cv.docx").write_text("x", encoding="utf-8")
    (ws / "data" / "candidates.json").write_text("{}", encoding="utf-8")
    (ws / "~$letter.docx").write_text("x", encoding="utf-8")
    (ws / "daily.md").write_text("brief", encoding="utf-8")
    assert history.commit(ws).startswith("committed")
    tracked = history.git(ws, "ls-files").stdout.split()
    assert sorted(tracked) == [".gitignore", "daily.md"]
    assert (ws / ".gitignore").read_text(encoding="utf-8") == "*.tmp\n"          # untouched
    exclude = (ws / ".git" / "info" / "exclude").read_text(encoding="utf-8")
    assert all(line in exclude.splitlines() for line in history.IGNORE)
    (ws / "daily.md").write_text("brief 2", encoding="utf-8")
    history.commit(ws)
    assert (ws / ".git" / "info" / "exclude").read_text(encoding="utf-8") == exclude   # written once


def test_a_workspace_inside_another_repo_isnt_committed(tool, sample):
    git(sample.parent, "init", "-q")
    tool("setup_check.py", "--init")
    assert not (sample / ".git").exists()
    out = tool("history.py", "commit").stdout
    assert out.startswith("no history: the workspace is inside another repo")
    assert git(sample.parent, "rev-list", "--all") == ""


def history_check(tool):
    checks = json.loads(tool("setup_check.py", "--json").stdout)["checks"]
    return next(c for c in checks if c["item"] == "workspace history (git)")


def test_setup_check_warns_without_a_history(tool, sample):
    c = history_check(tool)
    assert c["status"] == "warn" and c["fix"] == "no workspace history: python engine/tools/setup_check.py --init"
    tool("setup_check.py", "--init")
    assert history_check(tool)["status"] == "ok"


def test_setup_check_warns_inside_another_repo(tool, sample):
    git(sample.parent, "init", "-q")
    c = history_check(tool)
    assert c["status"] == "warn" and "inside another repo" in c["fix"]


def test_routine_commits_at_the_end():
    routine = (ENGINE / "ROUTINE.md").read_text(encoding="utf-8")
    assert routine.index("python engine/tools/history.py commit") > routine.index("8. Write daily/<today>.md")
