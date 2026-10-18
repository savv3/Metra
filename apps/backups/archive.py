"""Backup archives: a consistent copy of the SQLite database plus media files.

The database is copied with SQLite's online backup API, which gives a
consistent snapshot while the app keeps writing. Copying the file itself is
never safe for a database in WAL mode.
"""

import json
import os
import shutil
import sqlite3
import tarfile
import tempfile
from pathlib import Path

PREFIX = "scr-backup-"
SUFFIX = ".tar.gz"
FORMAT = 1
DB_NAME = "db.sqlite3"
MEDIA_NAME = "media"
MANIFEST_NAME = "manifest.json"


class ArchiveError(Exception):
    pass


def archive_name(moment):
    return f"{PREFIX}{moment:%Y%m%d-%H%M%S}{SUFFIX}"


def is_archive_name(name):
    return name.startswith(PREFIX) and name.endswith(SUFFIX)


def copy_database(source, destination):
    """Copy a live SQLite database into a new single-file database."""
    src = sqlite3.connect(source)
    dst = sqlite3.connect(destination)
    try:
        src.backup(dst)
        dst.execute("PRAGMA journal_mode=DELETE")
        (result,) = dst.execute("PRAGMA integrity_check").fetchone()
        if result != "ok":
            raise ArchiveError(f"The database copy failed its integrity check: {result}")
    finally:
        dst.close()
        src.close()


def create_archive(db_path, media_dir, out_dir, moment):
    """Write ``<out_dir>/scr-backup-<time>.tar.gz`` and return its path."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / archive_name(moment)
    partial = target.with_name(target.name + ".partial")
    with tempfile.TemporaryDirectory(dir=out_dir) as tmp:
        db_copy = Path(tmp) / DB_NAME
        copy_database(db_path, db_copy)
        manifest = Path(tmp) / MANIFEST_NAME
        manifest.write_text(json.dumps({"format": FORMAT, "created": moment.isoformat()}))
        with tarfile.open(partial, "w:gz") as tar:
            tar.add(manifest, MANIFEST_NAME)
            tar.add(db_copy, DB_NAME)
            if Path(media_dir).is_dir():
                tar.add(media_dir, MEDIA_NAME)
    os.chmod(partial, 0o600)  # the archive holds personal data
    partial.replace(target)
    return target


def local_archives(out_dir):
    """Archive paths in ``out_dir``, oldest first (names sort by time)."""
    out_dir = Path(out_dir)
    if not out_dir.is_dir():
        return []
    return sorted(p for p in out_dir.iterdir() if p.is_file() and is_archive_name(p.name))


def prune_local(out_dir, keep):
    """Delete all but the ``keep`` newest archives; return the deleted paths."""
    archives = local_archives(out_dir)
    old = archives[:-keep] if keep > 0 else archives
    for path in old:
        path.unlink()
    return old


def extract_archive(path, workdir):
    """Unpack an archive into ``workdir``; return (database path, media dir or None)."""
    try:
        with tarfile.open(path, "r:gz") as tar:
            tar.extractall(workdir, filter="data")  # refuses absolute paths and ../
    except (tarfile.TarError, OSError) as error:
        raise ArchiveError(f"Cannot read {path}: {error}") from error
    workdir = Path(workdir)
    try:
        manifest = json.loads((workdir / MANIFEST_NAME).read_text())
    except (OSError, ValueError) as error:
        raise ArchiveError(f"{path} is not a Small Company Register backup.") from error
    if manifest.get("format") != FORMAT or not (workdir / DB_NAME).is_file():
        raise ArchiveError(f"{path} is not a backup this version can restore.")
    media = workdir / MEDIA_NAME
    return workdir / DB_NAME, media if media.is_dir() else None


def restore_database(source, destination):
    """Replace the contents of ``destination`` with the database in ``source``."""
    src = sqlite3.connect(source)
    dst = sqlite3.connect(destination)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def restore_media(source, media_dir):
    """Make ``media_dir`` an exact copy of the backed-up media (or empty)."""
    media_dir = Path(media_dir)
    if media_dir.exists():
        shutil.rmtree(media_dir)
    if source is not None:
        shutil.copytree(source, media_dir)
    else:
        media_dir.mkdir(parents=True)
