"""Engine version: VERSION, version.py, setup_check and the changelog agree (S1-11)."""
import json
import re

from conftest import ENGINE

import version

SEMVER = re.compile(r"^\d+\.\d+\.\d+(-dev)?$")


def test_version_file():
    assert SEMVER.match(version.version()), version.version()
    assert version.describe().startswith(version.version())


def test_setup_check_prints_version(tool):
    assert tool("setup_check.py").stdout.splitlines()[0].startswith(f"engine {version.version()}")
    assert json.loads(tool("setup_check.py", "--json").stdout)["engine_version"] == version.version()


def test_changelog_has_this_version():
    text = (ENGINE / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [Unreleased]" in text
    v = version.version()
    if not v.endswith("-dev"):  # a release: its section must exist
        assert f"## [{v}] - " in text


def test_version_file_with_bom(tmp_path, monkeypatch):
    f = tmp_path / "VERSION"
    f.write_bytes("\ufeff0.4.0-dev\r\n".encode("utf-8"))  # as PowerShell's Set-Content -Encoding utf8 writes it
    monkeypatch.setattr(version, "VERSION_FILE", f)
    assert version.version() == "0.4.0-dev"
