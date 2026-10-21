"""Snapshots: a consistent copy of the SQLite database plus uploaded files,
in one archive.

The database is copied with SQLite's online backup API, which gives a
consistent copy while the app keeps writing. Copying the file itself is
never safe for a database in WAL mode.

A snapshot's file name says when it was taken, what triggered it and which
version of Metra took it, for example
``metra-snapshot-20261021-023000-nightly-0.3.0.tar.gz``, so snapshots can be
listed and kept on a schedule from their names alone, here and offsite.
"""

import datetime
import json
import os
import re
import shutil
import sqlite3
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path

PREFIX = "metra-snapshot-"
SUFFIX = ".tar.gz"
FORMAT = 2
NAME = re.compile(
    r"^metra-snapshot-(?P<time>\d{8}-\d{6})-(?P<trigger>[a-z]+)-(?P<version>[0-9A-Za-z.]+)\.tar\.gz$"
)
DB_NAME = "db.sqlite3"
MEDIA_NAME = "media"
MANIFEST_NAME = "manifest.json"


class ArchiveError(Exception):
    pass


@dataclass(frozen=True)
class Info:
    """What a snapshot's file name says about it."""

    name: str
    taken: datetime.datetime  # local time, without a time zone
    trigger: str
    version: str


def archive_name(moment, trigger, version):
    version = re.sub(r"[^0-9A-Za-z.]", "", version) or "0"
    return f"{PREFIX}{moment:%Y%m%d-%H%M%S}-{trigger}-{version}{SUFFIX}"


def parse_name(name):
    """The Info in a snapshot's name, or None for any other file."""
    match = NAME.match(name)
    if not match:
        return None
    taken = datetime.datetime.strptime(match["time"], "%Y%m%d-%H%M%S")
    return Info(name, taken, match["trigger"], match["version"])


def is_archive_name(name):
    return parse_name(name) is not None


def archive_time(name):
    """The time stamp in a snapshot's name; sorts snapshots oldest first."""
    return name.removeprefix(PREFIX)


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


def create_archive(db_path, media_dir, out_dir, moment, trigger="manual", version="0"):
    """Write a snapshot into ``out_dir`` and return its path."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / archive_name(moment, trigger, version)
    partial = target.with_name(target.name + ".partial")
    with tempfile.TemporaryDirectory(dir=out_dir) as tmp:
        db_copy = Path(tmp) / DB_NAME
        copy_database(db_path, db_copy)
        manifest = Path(tmp) / MANIFEST_NAME
        manifest.write_text(
            json.dumps(
                {
                    "format": FORMAT,
                    "created": moment.isoformat(),
                    "trigger": trigger,
                    "version": version,
                }
            )
        )
        with tarfile.open(partial, "w:gz") as tar:
            tar.add(manifest, MANIFEST_NAME)
            tar.add(db_copy, DB_NAME)
            if Path(media_dir).is_dir():
                tar.add(media_dir, MEDIA_NAME)
    os.chmod(partial, 0o600)  # the archive holds personal data
    partial.replace(target)
    return target


def local_archives(out_dir):
    """Archive paths in ``out_dir``, oldest first."""
    out_dir = Path(out_dir)
    if not out_dir.is_dir():
        return []
    archives = (p for p in out_dir.iterdir() if p.is_file() and is_archive_name(p.name))
    return sorted(archives, key=lambda p: archive_time(p.name))


def prune_local(out_dir, policy, now):
    """Delete the snapshots ``policy`` no longer keeps; return the deleted paths."""
    archives = {path.name: path for path in local_archives(out_dir)}
    old = [archives[name] for name in policy.to_delete(archives, now)]
    for path in old:
        path.unlink()
    return old


def manifest_version(workdir):
    """The Metra version an unpacked snapshot was taken with ("" if unknown)."""
    try:
        return json.loads((Path(workdir) / MANIFEST_NAME).read_text()).get("version", "")
    except (OSError, ValueError):
        return ""


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
        raise ArchiveError(f"{path} is not a Metra backup.") from error
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
