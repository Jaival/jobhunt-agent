"""Release channels: stable updates to the newest release tag only, next follows the next branch.

A local bare repo stands in for GitHub: main has the releases v0.5.0 and v0.6.0, next has a commit after them.
"""
import subprocess

import pytest

import upgrade
import version


def run(cwd, *args):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def commit(repo, ver, msg):
    (repo / "VERSION").write_text(ver + "\n", encoding="utf-8")
    run(repo, "add", "VERSION")
    run(repo, "commit", "-q", "-m", msg)
    return run(repo, "rev-parse", "HEAD")


@pytest.fixture
def remote(tmp_path, monkeypatch):
    """(dev clone, workspace, shas): the workspace's engine/ is a clone at v0.5.0, before v0.6.0 was pushed."""
    for k, v in {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t",
                 "GIT_COMMITTER_EMAIL": "t@example.com", "GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig")}.items():
        monkeypatch.setenv(k, v)
    bare, dev, ws = tmp_path / "origin.git", tmp_path / "dev", tmp_path / "ws"
    run(tmp_path, "init", "-q", "--bare", "-b", "main", str(bare))
    run(tmp_path, "clone", "-q", str(bare), str(dev))
    sha = {"v0.5.0": commit(dev, "0.5.0", "release 0.5.0")}
    run(dev, "tag", "v0.5.0")
    run(dev, "push", "-q", "origin", "main", "v0.5.0")
    ws.mkdir()
    run(ws, "clone", "-q", str(bare), "engine")
    (ws / "config.yaml").write_text("applicant: Test\n", encoding="utf-8")

    sha["v0.6.0"] = commit(dev, "0.6.0", "release 0.6.0")
    run(dev, "tag", "v0.6.0")
    run(dev, "tag", "v0.7.0-rc1")                           # not a release tag: ignored
    run(dev, "switch", "-q", "-c", "next")
    sha["next"] = commit(dev, "0.7.0-dev", "work on next")
    run(dev, "push", "-q", "origin", "main", "next", "--tags")

    monkeypatch.setattr(upgrade, "ROOT", ws)
    monkeypatch.setattr(upgrade, "ENGINE", ws / "engine")
    return dev, ws, sha


def head(ws):
    return run(ws / "engine", "rev-parse", "HEAD")


def test_parse_orders_dev_below_release():
    assert version.parse("0.6.0-dev") < version.parse("v0.6.0") < version.parse("0.10.0")
    assert version.parse("1.0") is None


def test_channel_validates():
    assert version.channel({}) == "stable" and version.channel({"engine_channel": "Next"}) == "next"
    with pytest.raises(ValueError):
        version.channel({"engine_channel": "beta"})


def test_stable_status_and_apply_go_to_newest_tag(remote, capsys):
    _, ws, sha = remote
    eng = ws / "engine"
    upgrade.cmd_status(None)
    out = capsys.readouterr().out
    assert "channel: stable" in out and "update: release v0.6.0, engine version there: 0.6.0" in out
    assert "work on next" not in out                        # commits on next never reach a stable user
    assert version.newest_tag(eng) == "v0.6.0"
    upgrade.cmd_prepare(None)
    upgrade.cmd_apply(None)
    assert head(ws) == sha["v0.6.0"]
    assert version.update("stable", eng) is None            # up to date now
    p, state = upgrade.load_state()                      # a second update with nothing new stops
    state["steps"].remove("apply")
    upgrade.save_state(p, state)
    with pytest.raises(upgrade.UpgradeError, match="no update on the stable channel"):
        upgrade.cmd_apply(None)
    assert head(ws) == sha["v0.6.0"]


def test_next_channel_follows_next(remote):
    _, ws, sha = remote
    (ws / "config.yaml").write_text("applicant: Test\nengine_channel: next\n", encoding="utf-8")
    assert upgrade.fetch() and version.update("next", ws / "engine")[0] == "origin/next"
    upgrade.cmd_prepare(None)
    upgrade.cmd_apply(None)
    assert head(ws) == sha["next"]
    assert run(ws / "engine", "rev-parse", "--abbrev-ref", "HEAD") == "next"


def test_stable_never_downgrades_an_engine_ahead_of_the_releases(remote):
    _, ws, sha = remote
    eng = ws / "engine"
    run(eng, "fetch", "-q", "--tags")
    run(eng, "checkout", "-q", "next")                       # a former tester, now back on stable
    assert version.update("stable", eng) is None


def test_rollback_after_stable_update(remote):
    _, ws, sha = remote
    upgrade.cmd_prepare(None)
    upgrade.cmd_apply(None)
    upgrade.cmd_rollback(None)
    assert head(ws) == sha["v0.5.0"]


def test_setup_check_reports_the_release(remote, monkeypatch):
    _, ws, _ = remote
    monkeypatch.delenv("JOBHUNT_OFFLINE", raising=False)
    monkeypatch.setattr(version, "ENGINE", ws / "engine")
    import setup_check
    assert setup_check.engine_update("stable") == (("v0.6.0", "release v0.6.0"), True)
    assert setup_check.engine_update("next")[0][1] == "2 new change(s) on next"


def test_setup_check_says_when_the_update_check_did_not_run(monkeypatch):
    import setup_check
    monkeypatch.delenv("JOBHUNT_OFFLINE", raising=False)
    monkeypatch.setattr(setup_check, "git", lambda *a, **k: None)
    assert setup_check.engine_update("stable") == (None, False)
    monkeypatch.setenv("JOBHUNT_OFFLINE", "1")
    assert setup_check.engine_update("stable") == (None, None)


def test_migrate_adds_the_channel(tool):
    r = tool("upgrade.py", "migrate", "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "engine_channel: stable" in r.stdout
