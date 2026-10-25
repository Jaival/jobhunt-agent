"""atomic.write_text: the file is either the old version or the new one, and no temp files pile up (S1-6)."""
import os
import stat
import time

import pytest

import atomic


@pytest.fixture
def target(tmp_path):
    p = tmp_path / "data" / "seen_jobs.csv"
    atomic.write_text(p, "old\n")
    return p


def leftovers(p):
    return sorted(x.name for x in p.parent.iterdir() if x != p)


def test_round_trip(target):
    atomic.write_text(target, "new\r\n", newline="")
    assert target.read_bytes() == b"new\r\n"
    assert leftovers(target) == []


def test_interrupted_write_keeps_old_file(target, monkeypatch):
    def boom(fd):
        raise KeyboardInterrupt  # e.g. the scheduled run is stopped halfway
    monkeypatch.setattr(atomic.os, "fsync", boom)
    with pytest.raises(KeyboardInterrupt):
        atomic.write_text(target, "new\n")
    assert target.read_text() == "old\n" and leftovers(target) == []


def test_replace_retries_while_file_is_in_use(target, monkeypatch):
    real, calls = os.replace, []
    def flaky(src, dst):
        calls.append(1)
        if len(calls) < 3:
            raise PermissionError(13, "in use by another process")
        real(src, dst)
    monkeypatch.setattr(atomic.os, "replace", flaky)
    monkeypatch.setattr(atomic.time, "sleep", lambda _: None)
    atomic.write_text(target, "new\n")
    assert target.read_text() == "new\n" and len(calls) == 3 and leftovers(target) == []


def test_replace_gives_up_and_keeps_old_file(target, monkeypatch):
    def locked(src, dst):
        raise PermissionError(13, "open in Excel")
    monkeypatch.setattr(atomic.os, "replace", locked)
    monkeypatch.setattr(atomic.time, "sleep", lambda _: None)
    with pytest.raises(PermissionError):
        atomic.write_text(target, "new\n")
    assert target.read_text() == "old\n" and leftovers(target) == []


def test_stale_temp_files_are_removed(target):
    stale = target.parent / f".{target.name}.abc.tmp"
    fresh = target.parent / f".{target.name}.def.tmp"  # another process may still be writing this one
    stale.write_text("x")
    fresh.write_text("x")
    old = time.time() - atomic.STALE - 60
    os.utime(stale, (old, old))
    atomic.write_text(target, "new\n")
    assert leftovers(target) == [fresh.name]


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes")
def test_keeps_the_file_mode(target):
    os.chmod(target, 0o644)
    atomic.write_text(target, "new\n")
    assert stat.S_IMODE(target.stat().st_mode) == 0o644
