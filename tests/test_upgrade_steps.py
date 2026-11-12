"""upgrade.py prepare / apply / rollback / finish against a local git remote (the fixture of test_channels.py)."""
import datetime as dt
import json

import pytest

import upgrade
import test_channels
from test_channels import head

remote = test_channels.remote  # the fixture; an import here would be "redefined" by every test's parameter


def state_of(ws):
    return json.loads(upgrade.state_path().read_text(encoding="utf-8"))


def today():
    return f"{dt.date.today():%Y-%m-%d}"


def backup_of(ws):
    return ws / "backups" / state_of(ws)["backup"]


def test_prepare_backs_up_the_workspace_and_the_engine(remote):
    _, ws, sha = remote
    (ws / "CLAUDE.md").write_text("# me\n", encoding="utf-8")
    (ws / "cv").mkdir()
    (ws / "cv" / "a.txt").write_text("cv\n", encoding="utf-8")
    upgrade.cmd_prepare(None)
    backup = ws / "backups" / f"pre-upgrade-{today()}"
    assert (backup / "config.yaml").is_file() and (backup / "CLAUDE.md").is_file()
    assert (backup / "cv" / "a.txt").is_file()
    assert (backup / "engine-old" / "VERSION").read_text(encoding="utf-8").strip() == "0.5.0"
    assert not (backup / "engine-old" / ".git").exists()
    state = json.loads((backup / "upgrade.json").read_text(encoding="utf-8"))
    assert state["steps"] == ["prepare"] and state["stash"] is None
    assert state["old_commit"] == sha["v0.5.0"] and state["edits"] == [] and state["layout_existed"] is False


def test_a_second_prepare_on_the_same_day_gets_its_own_folder(remote):
    _, ws, _ = remote
    upgrade.cmd_prepare(None)
    upgrade.cmd_prepare(None)
    assert (ws / "backups" / f"pre-upgrade-{today()}-2").is_dir()
    assert state_of(ws)["backup"].endswith("-2")


def test_prepare_saves_local_edits_as_a_patch(remote):
    _, ws, _ = remote
    (ws / "engine" / "VERSION").write_text("0.5.0\nlocal\n", encoding="utf-8")
    (ws / "engine" / "local.txt").write_text("mine", encoding="utf-8")
    upgrade.cmd_prepare(None)
    state = state_of(ws)
    assert "VERSION" in state["edits"] and "local.txt" in state["edits"]
    assert "+local" in (backup_of(ws) / "engine-local-changes.patch").read_text(encoding="utf-8")


def test_apply_stashes_local_edits_and_moves_to_the_release(remote):
    _, ws, sha = remote
    (ws / "engine" / "local.txt").write_text("mine", encoding="utf-8")
    upgrade.cmd_prepare(None)
    upgrade.cmd_apply(None)
    assert head(ws) == sha["v0.6.0"]
    assert not (ws / "engine" / "local.txt").exists()
    state = state_of(ws)
    assert state["stash"] and state["new_commit"] == sha["v0.6.0"] and state["steps"] == ["prepare", "apply"]


def test_apply_twice_stops(remote):
    upgrade.cmd_prepare(None)
    upgrade.cmd_apply(None)
    with pytest.raises(upgrade.UpgradeError, match="already applied"):
        upgrade.cmd_apply(None)


def test_rollback_restores_the_engine_the_edits_and_the_config(remote):
    _, ws, sha = remote
    (ws / "engine" / "local.txt").write_text("mine", encoding="utf-8")
    upgrade.cmd_prepare(None)
    upgrade.cmd_apply(None)
    (ws / "config.yaml").write_text("applicant: Changed\n", encoding="utf-8")
    upgrade.cmd_rollback(None)
    assert head(ws) == sha["v0.5.0"]
    assert (ws / "engine" / "local.txt").read_text(encoding="utf-8") == "mine"
    assert (ws / "config.yaml").read_text(encoding="utf-8") == "applicant: Test\n"
    assert state_of(ws)["steps"][-1] == "rollback"


def test_rollback_moves_a_layout_the_upgrade_created(remote):
    _, ws, _ = remote
    upgrade.cmd_prepare(None)
    upgrade.cmd_apply(None)
    (ws / "cv").mkdir()
    (ws / "cv" / "layout.yaml").write_text("fields: {}\n", encoding="utf-8")
    upgrade.cmd_rollback(None)
    assert not (ws / "cv" / "layout.yaml").exists()
    assert (backup_of(ws) / "layout.yaml.from-upgrade").is_file()


def test_finish_removes_the_engine_copy_and_keeps_the_backup(remote):
    _, ws, _ = remote
    upgrade.cmd_prepare(None)
    upgrade.cmd_apply(None)
    backup = backup_of(ws)
    (backup / "test").mkdir()
    (backup / "test" / "x.txt").write_text("x", encoding="utf-8")
    upgrade.cmd_finish(None)
    assert not (backup / "engine-old").exists() and not (backup / "test").exists()
    assert (backup / "config.yaml").is_file()
    assert state_of(ws)["steps"][-1] == "finish"


def test_a_step_without_prepare_stops_with_a_message(remote):
    with pytest.raises(upgrade.UpgradeError, match="prepare"):
        upgrade.cmd_apply(None)
    with pytest.raises(upgrade.UpgradeError, match="prepare"):
        upgrade.cmd_rollback(None)


def test_compare_files(tmp_path):
    import docx

    def write(name, text):
        d = docx.Document()
        d.add_paragraph(text)
        d.save(tmp_path / name)
        return tmp_path / name

    a, b, c = write("a.docx", "Same text"), write("b.docx", "Same text"), write("c.docx", "Other text")
    assert upgrade.compare_files(a, a)[0] == "identical"
    verdict, diff = upgrade.compare_files(a, c)
    assert verdict == "text differs"
    assert any(ln.startswith("-") for ln in diff) and any(ln.startswith("+") for ln in diff)
    verdict, _ = upgrade.compare_files(a, b)  # two saves can differ in zip metadata
    assert verdict == "identical" or verdict.startswith("same text")


def test_apply_without_an_update_leaves_local_edits_in_place(remote):
    _, ws, sha = remote
    upgrade.cmd_prepare(None)
    upgrade.cmd_apply(None)                                   # now at v0.6.0, the newest release
    upgrade.cmd_prepare(None)                                 # a second run: nothing newer
    (ws / "engine" / "local.txt").write_text("mine", encoding="utf-8")
    with pytest.raises(upgrade.UpgradeError, match="no update"):
        upgrade.cmd_apply(None)
    assert (ws / "engine" / "local.txt").read_text(encoding="utf-8") == "mine"
    assert state_of(ws)["stash"] is None


def test_apply_saves_the_stash_before_it_moves_the_engine(remote, monkeypatch):
    _, ws, sha = remote
    (ws / "engine" / "local.txt").write_text("mine", encoding="utf-8")
    upgrade.cmd_prepare(None)
    real = upgrade.git

    def failing(*args, **kw):
        if args[:1] == ("checkout",):
            raise upgrade.UpgradeError("checkout failed")
        return real(*args, **kw)
    monkeypatch.setattr(upgrade, "git", failing)
    with pytest.raises(upgrade.UpgradeError, match="checkout failed"):
        upgrade.cmd_apply(None)
    assert state_of(ws)["stash"]                               # rollback can bring the edits back


def test_rollback_restores_the_config_when_the_stash_does_not_apply(remote, monkeypatch, capsys):
    _, ws, sha = remote
    (ws / "engine" / "local.txt").write_text("mine", encoding="utf-8")
    upgrade.cmd_prepare(None)
    upgrade.cmd_apply(None)
    (ws / "config.yaml").write_text("applicant: Changed\n", encoding="utf-8")
    real = upgrade.git

    def failing(*args, **kw):
        if args[:2] == ("stash", "apply"):
            raise upgrade.UpgradeError("git stash apply failed: conflict")
        return real(*args, **kw)
    monkeypatch.setattr(upgrade, "git", failing)
    assert upgrade.cmd_rollback(None) == 0
    assert (ws / "config.yaml").read_text(encoding="utf-8") == "applicant: Test\n"
    assert head(ws) == sha["v0.5.0"]
    out = capsys.readouterr().out
    assert "NOT restored" in out and "engine-local-changes.patch" in out


@pytest.mark.parametrize("text", ["{broken", "[]", '{"backup": "x"}'])
def test_a_damaged_state_file_stops_with_a_message(remote, text):
    _, ws, sha = remote
    upgrade.cmd_prepare(None)
    upgrade.state_path().write_text(text, encoding="utf-8")
    with pytest.raises(upgrade.UpgradeError, match="upgrade.json"):
        upgrade.cmd_apply(None)
