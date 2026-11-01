"""Workspace history (S4-4): setup_check.py --init starts a local git repo unless there is one; history.py commit
records each daily run. Nothing is ever pushed."""
import datetime as dt
import json
import subprocess

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


def test_a_workspace_inside_another_repo_isnt_committed(tool, sample):
    git(sample.parent, "init", "-q")
    tool("setup_check.py", "--init")
    assert not (sample / ".git").exists()
    out = tool("history.py", "commit").stdout
    assert out.startswith("no history: the workspace is inside another repo")
    assert git(sample.parent, "rev-list", "--all") == ""


def test_routine_commits_at_the_end():
    routine = (ENGINE / "ROUTINE.md").read_text(encoding="utf-8")
    assert routine.index("python engine/tools/history.py commit") > routine.index("8. Write daily/<today>.md")
