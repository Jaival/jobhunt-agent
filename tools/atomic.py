"""Write a file so that it's always either the old version or the new one, never half of each.

Used for the files a run that's cut off must not damage: the seen-jobs ledger and data/candidates.json. The text
goes to a temp file in the same folder (".<name>.<random>.tmp"), is flushed to disk, then swapped in with
os.replace. A failure inside Python removes the temp file. A killed process can't, so temp files older than an
hour are removed on the next write.
"""
import os
import stat
import tempfile
import time
from pathlib import Path

STALE = 3600       # seconds before a leftover temp file counts as abandoned
TRIES = 5          # os.replace attempts while Windows reports the target as in use


def write_text(path, text, encoding="utf-8", newline=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    remove_stale(path)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline=newline) as f:
            fd = None  # the file object owns it now
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, mode_for(path))  # mkstemp makes it 0600; keep the file's own mode
        replace(tmp, path)
    except BaseException:
        if fd is not None:
            os.close(fd)
        Path(tmp).unlink(missing_ok=True)
        raise
    sync_dir(path.parent)


def mode_for(path):
    try:
        return stat.S_IMODE(path.stat().st_mode)
    except FileNotFoundError:
        umask = os.umask(0)
        os.umask(umask)
        return 0o666 & ~umask


def replace(tmp, path):
    """os.replace, retried briefly: on Windows a virus scanner or sync client can hold the file for a moment."""
    for i in range(TRIES):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if i == TRIES - 1:
                raise
            time.sleep(0.2 * (i + 1))


def sync_dir(folder):
    """Make the rename itself durable (POSIX; Windows has no directory fsync)."""
    if os.name != "posix":
        return
    fd = os.open(folder, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def remove_stale(path):
    cutoff = time.time() - STALE
    for p in path.parent.glob(f".{path.name}.*.tmp"):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
        except OSError:
            pass
