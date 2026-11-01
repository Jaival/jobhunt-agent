"""release_notes.py: the release workflow's tag, VERSION and CHANGELOG check (S4-2)."""
import re

import pytest

from conftest import ENGINE

from release_notes import ReleaseError, notes

CHANGELOG = """# Changelog

## [Unreleased]

## [1.0.0] - 2026-12-18: versioned & interactive

### Added
- Commands.

## [0.5.0] - 2026-10-30: grounded & modular

### Fixed
- Something.

[Unreleased]: https://example.com/compare/v1.0.0...next
[1.0.0]: https://example.com/compare/v0.5.0...v1.0.0
"""


@pytest.fixture
def engine(tmp_path):
    (tmp_path / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")
    return tmp_path


def test_notes_are_the_section(engine):
    title, body = notes("v1.0.0", engine)
    assert title == "v1.0.0: versioned & interactive"
    assert body == "### Added\n- Commands.\n"
    (engine / "VERSION").write_text("0.5.0", encoding="utf-8")
    assert notes("v0.5.0", engine)[1] == "### Fixed\n- Something.\n"   # the last section stops at the links


@pytest.mark.parametrize("tag, version, error", [
    ("v1.0", "1.0.0", "isn't vX.Y.Z"),
    ("v1.0.0-rc1", "1.0.0", "isn't vX.Y.Z"),
    ("v1.0.0", "1.1.0-dev", "VERSION is 1.1.0-dev"),
    ("v0.9.0", "0.9.0", "no '## [0.9.0]"),
])
def test_mismatch_stops(engine, tag, version, error):
    (engine / "VERSION").write_text(version, encoding="utf-8")
    with pytest.raises(ReleaseError, match=re.escape(error)):
        notes(tag, engine)


def test_empty_section_stops(engine):
    (engine / "CHANGELOG.md").write_text(CHANGELOG.replace("### Added\n- Commands.\n", ""), encoding="utf-8")
    with pytest.raises(ReleaseError, match="empty"):
        notes("v1.0.0", engine)


def test_every_released_section_has_notes(tmp_path):
    """Each release in the real CHANGELOG.md passes with its own VERSION: the heading format matches."""
    text = (ENGINE / "CHANGELOG.md").read_text(encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text(text, encoding="utf-8")
    released = re.findall(r"^## \[(\d+\.\d+\.\d+)\] - ", text, re.M)
    assert "0.5.0" in released
    for v in released:
        (tmp_path / "VERSION").write_text(v, encoding="utf-8")
        title, body = notes(f"v{v}", tmp_path)
        assert title.startswith(f"v{v}: ") and "## [" not in body
