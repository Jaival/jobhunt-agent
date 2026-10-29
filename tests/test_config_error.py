"""config.py raises ConfigError; a tool run from the command line prints only its message and exits with 1."""
import sys

import pytest
from conftest import runner


def test_missing_config_is_a_clean_message(tmp_path):
    r = runner(tmp_path)("ledger.py", "check", "Acme", "Intern")
    assert r.returncode == 1
    assert r.stderr.startswith("config.yaml not found in ") and "Traceback" not in r.stderr


def test_incomplete_config_names_the_keys(tmp_path):
    (tmp_path / "config.yaml").write_text("applicant: A\n", encoding="utf-8")
    r = runner(tmp_path)("build_application.py", "x")
    assert r.returncode == 1 and "Traceback" not in r.stderr
    assert r.stderr.strip() == "config.yaml is missing: file_prefix, master_cv, master_letter, variants, letter_city"


def test_a_tools_own_key_is_a_clean_message(tool, sample):
    with (sample / "config.yaml").open("a", encoding="utf-8") as f:
        f.write("ledger_expiry_days: soon\n")
    r = tool("ledger.py", "check", "Acme", "Intern")
    assert r.returncode == 1 and "Traceback" not in r.stderr
    assert "ledger_expiry_days must be a whole number" in r.stderr


def test_importing_raises_instead_of_exiting(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBHUNT_ROOT", str(tmp_path))
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.delitem(sys.modules, "config", raising=False)
    with pytest.raises(Exception) as e:
        import config  # noqa: F401
    assert type(e.value).__name__ == "ConfigError"
    monkeypatch.delitem(sys.modules, "config", raising=False)   # the next test imports it fresh
