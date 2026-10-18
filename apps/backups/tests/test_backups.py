import datetime
import sqlite3
import subprocess
import tarfile
import threading

import pytest
from auditlog.models import LogEntry
from django.core.management import CommandError, call_command
from django.urls import reverse
from django.utils import timezone

from apps.backups import archive
from apps.backups.models import BackupRun
from apps.backups.rclone import RcloneError, Remote
from apps.backups.service import run_backup
from apps.backups.tasks import nightly_backup, schedule_time

MOMENT = datetime.datetime(2026, 10, 18, 2, 30, tzinfo=datetime.UTC)
SECRET = "very-secret-crypt-password"
REMOTE = {
    "remote_type": "s3",
    "remote_path": "bucket/scr",
    "encryption_password": SECRET,
    "s3_provider": "Other",
    "s3_endpoint": "s3.example.com",
    "s3_region": "eu-north-1",
    "s3_access_key_id": "AKIDEXAMPLE",
    "s3_secret_access_key": "s3-secret-value",
    "host": "",
    "port": "",
    "user": "",
    "password": "",
    "sftp_key_file": "",
}


def make_database(path, rows=0):
    db = sqlite3.connect(path)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("CREATE TABLE item (id INTEGER PRIMARY KEY, pair INTEGER, value TEXT)")
    with db:
        db.executemany(
            "INSERT INTO item (pair, value) VALUES (?, ?)", [(i, "x") for i in range(rows)]
        )
    return db


def count(path):
    db = sqlite3.connect(path)
    try:
        return db.execute("SELECT count(*) FROM item").fetchone()[0]
    finally:
        db.close()


class FakeRclone:
    """Stands in for subprocess.run; records commands and answers like rclone."""

    def __init__(self, listing="", fail=None):
        self.calls = []
        self.listing = listing
        self.fail = fail

    def __call__(self, command, input=None, env=None, **kwargs):
        self.calls.append({"command": command, "input": input, "env": env})
        verb = command[1]
        if verb == self.fail:
            raise subprocess.CalledProcessError(
                1, command, stderr=f"access denied for {SECRET} and s3-secret-value"
            )
        out = {"obscure": f"obscured({input})", "lsf": self.listing}.get(verb, "")
        return subprocess.CompletedProcess(command, 0, stdout=out, stderr="")

    def verbs(self):
        return [call["command"][1] for call in self.calls]


# The database copy


def test_copy_is_consistent_while_the_app_writes(tmp_path):
    source = tmp_path / "live.sqlite3"
    make_database(source, rows=2000).close()
    stop = threading.Event()

    def write():
        db = sqlite3.connect(source, timeout=10)
        n = 0
        while not stop.is_set():
            with db:  # each transaction adds two rows, so a torn copy has an odd count
                db.execute("INSERT INTO item (pair, value) VALUES (?, ?)", (n, "a" * 500))
                db.execute("INSERT INTO item (pair, value) VALUES (?, ?)", (n, "b" * 500))
            n += 1
        db.close()

    writer = threading.Thread(target=write)
    writer.start()
    try:
        copies = []
        for i in range(5):
            copy = tmp_path / f"copy{i}.sqlite3"
            archive.copy_database(source, copy)
            copies.append(copy)
    finally:
        stop.set()
        writer.join()

    for copy in copies:
        assert count(copy) % 2 == 0
        assert count(copy) >= 2000
        db = sqlite3.connect(copy)
        assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert db.execute("PRAGMA journal_mode").fetchone() == ("delete",)
        db.close()
    assert not (tmp_path / "copy0.sqlite3-wal").exists()


def test_archive_holds_database_media_and_manifest(tmp_path):
    db = tmp_path / "db.sqlite3"
    make_database(db, rows=3).close()
    media = tmp_path / "media"
    (media / "uploads").mkdir(parents=True)
    (media / "uploads" / "karta.pdf").write_bytes(b"%PDF")

    path = archive.create_archive(db, media, tmp_path / "backups", MOMENT)

    assert path.name == "metra-backup-20261018-023000.tar.gz"
    assert path.stat().st_mode & 0o777 == 0o600
    with tarfile.open(path) as tar:
        names = set(tar.getnames())
    assert {"manifest.json", "db.sqlite3", "media/uploads/karta.pdf"} <= names
    assert not list((tmp_path / "backups").glob("*.partial"))


def test_restore_round_trip(tmp_path):
    db = tmp_path / "db.sqlite3"
    make_database(db, rows=7).close()
    media = tmp_path / "media"
    media.mkdir()
    (media / "a.txt").write_text("hej")
    path = archive.create_archive(db, media, tmp_path / "backups", MOMENT)

    fresh_db = tmp_path / "fresh.sqlite3"
    sqlite3.connect(fresh_db).close()
    fresh_media = tmp_path / "fresh-media"
    (fresh_media / "old.txt").parent.mkdir()
    (fresh_media / "old.txt").write_text("old")
    db_file, media_copy = archive.extract_archive(path, tmp_path / "extracted")
    archive.restore_database(db_file, fresh_db)
    archive.restore_media(media_copy, fresh_media)

    assert count(fresh_db) == 7
    assert (fresh_media / "a.txt").read_text() == "hej"
    assert not (fresh_media / "old.txt").exists()


def test_extract_refuses_files_that_are_not_backups(tmp_path):
    bogus = tmp_path / "bogus.tar.gz"
    with tarfile.open(bogus, "w:gz") as tar:
        note = tmp_path / "note.txt"
        note.write_text("hi")
        tar.add(note, "note.txt")

    with pytest.raises(archive.ArchiveError):
        archive.extract_archive(bogus, tmp_path / "out")


def test_local_retention_keeps_the_newest(tmp_path):
    for day in range(1, 6):
        (tmp_path / f"metra-backup-202610{day:02d}-023000.tar.gz").write_bytes(b"x")
    (tmp_path / "unrelated.txt").write_text("keep me")

    removed = archive.prune_local(tmp_path, keep=2)

    assert [p.name for p in removed] == [
        f"metra-backup-202610{day:02d}-023000.tar.gz" for day in (1, 2, 3)
    ]
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "metra-backup-20261004-023000.tar.gz",
        "metra-backup-20261005-023000.tar.gz",
        "unrelated.txt",
    ]


def test_archives_from_before_the_rename_sort_by_time(tmp_path):
    for name in (
        "scr-backup-20261001-023000.tar.gz",
        "metra-backup-20261002-023000.tar.gz",
        "scr-backup-20261003-023000.tar.gz",
    ):
        (tmp_path / name).write_bytes(b"x")

    removed = archive.prune_local(tmp_path, keep=1)

    assert [p.name for p in removed] == [
        "scr-backup-20261001-023000.tar.gz",
        "metra-backup-20261002-023000.tar.gz",
    ]


# rclone


def test_rclone_is_configured_through_the_environment_only():
    runner = FakeRclone()
    remote = Remote(REMOTE, runner)

    remote.upload(archive.Path("/data/backups/metra-backup-20261018-023000.tar.gz"))

    obscure, upload = runner.calls
    assert obscure["command"] == ["rclone", "obscure", "-"]
    assert obscure["input"] == SECRET  # through stdin, never the command line
    assert upload["command"] == [
        "rclone",
        "copyto",
        "/data/backups/metra-backup-20261018-023000.tar.gz",
        "scrcrypt:metra-backup-20261018-023000.tar.gz",
    ]
    env = upload["env"]
    assert env["RCLONE_CONFIG_SCRREMOTE_TYPE"] == "s3"
    assert env["RCLONE_CONFIG_SCRREMOTE_ENDPOINT"] == "s3.example.com"
    assert env["RCLONE_CONFIG_SCRREMOTE_SECRET_ACCESS_KEY"] == "s3-secret-value"
    assert env["RCLONE_CONFIG_SCRCRYPT_TYPE"] == "crypt"
    assert env["RCLONE_CONFIG_SCRCRYPT_REMOTE"] == "scrremote:bucket/scr"
    assert env["RCLONE_CONFIG_SCRCRYPT_PASSWORD"] == f"obscured({SECRET})"
    for call in runner.calls:
        assert not any(secret in " ".join(call["command"]) for secret in remote.secrets())


@pytest.mark.parametrize("kind, rclone_type", [("sftp", "sftp"), ("ftps", "ftp")])
def test_sftp_and_ftps_remotes(kind, rclone_type):
    config = dict(REMOTE, remote_type=kind, host="backup.example.com", user="scr", password="pw")
    runner = FakeRclone()

    Remote(config, runner).run("lsf", "scrcrypt:")

    env = runner.calls[-1]["env"]
    assert env["RCLONE_CONFIG_SCRREMOTE_TYPE"] == rclone_type
    assert env["RCLONE_CONFIG_SCRREMOTE_HOST"] == "backup.example.com"
    assert env["RCLONE_CONFIG_SCRREMOTE_PASS"] == "obscured(pw)"
    assert (env.get("RCLONE_CONFIG_SCRREMOTE_EXPLICIT_TLS") == "true") == (kind == "ftps")


def test_remote_retention_deletes_the_oldest():
    listing = "\n".join(f"metra-backup-202610{d:02d}-023000.tar.gz" for d in (3, 1, 2)) + "\nother"
    runner = FakeRclone(listing=listing)

    removed = Remote(REMOTE, runner).prune(keep=1)

    assert removed == ["metra-backup-20261001-023000.tar.gz", "metra-backup-20261002-023000.tar.gz"]
    deletes = [c["command"] for c in runner.calls if c["command"][1] == "deletefile"]
    assert deletes == [["rclone", "deletefile", f"scrcrypt:{name}"] for name in removed]


def test_remote_lists_archives_from_before_the_rename():
    listing = "metra-backup-20261020-023000.tar.gz\nscr-backup-20261019-023000.tar.gz\n"

    names = Remote(REMOTE, FakeRclone(listing=listing)).list()

    assert names == ["scr-backup-20261019-023000.tar.gz", "metra-backup-20261020-023000.tar.gz"]


def test_remote_needs_an_encryption_password():
    with pytest.raises(RcloneError, match="ENCRYPTION_PASSWORD"):
        Remote(dict(REMOTE, encryption_password=""))


def test_rclone_errors_never_show_secrets():
    remote = Remote(REMOTE, FakeRclone(fail="copyto"))

    with pytest.raises(RcloneError) as error:
        remote.upload(archive.Path("/x/metra-backup-1.tar.gz"))

    assert SECRET not in str(error.value)
    assert "s3-secret-value" not in str(error.value)


# Running a backup


@pytest.fixture
def live_db(tmp_path, settings, monkeypatch):
    """Point the backup at a real SQLite file (the test database lives in memory)."""
    db = tmp_path / "db.sqlite3"
    make_database(db, rows=5).close()
    monkeypatch.setattr("apps.backups.service.database_path", lambda: db)
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.BACKUP = dict(REMOTE, remote_type="", dir=tmp_path / "backups", keep=2, time="02:30")
    return db


@pytest.mark.django_db
def test_local_backup_is_recorded(live_db, settings):
    run = run_backup()

    assert run.success
    assert (settings.BACKUP["dir"] / run.archive_name).stat().st_size == run.size
    assert run.target == str(settings.BACKUP["dir"])
    assert LogEntry.objects.get_for_object(run).exists()


@pytest.mark.django_db
def test_backup_uploads_and_prunes_when_a_remote_is_set(live_db, settings):
    settings.BACKUP = dict(settings.BACKUP, remote_type="s3")
    runner = FakeRclone()

    run = run_backup(runner=runner)

    assert run.success
    assert runner.verbs() == ["obscure", "copyto", "lsf"]
    assert "S3 s3.example.com bucket/scr (encrypted)" in run.target


@pytest.mark.django_db
def test_failed_backup_is_recorded_without_secrets(live_db, settings):
    settings.BACKUP = dict(settings.BACKUP, remote_type="s3")

    run = run_backup(runner=FakeRclone(fail="copyto"))

    assert not run.success
    assert "access denied" in run.error
    assert SECRET not in run.error and "s3-secret-value" not in run.error
    entry = LogEntry.objects.get_for_object(run).latest("timestamp")
    assert SECRET not in str(entry.changes)


@pytest.mark.django_db
def test_backup_command_fails_loudly(live_db, settings):
    settings.BACKUP = dict(settings.BACKUP, remote_type="nfs")

    with pytest.raises(CommandError, match="must be one of"):
        call_command("backup")

    assert BackupRun.objects.get().success is False


def test_nightly_schedule_defaults_to_half_past_two():
    assert schedule_time("02:30") == (2, 30)
    assert nightly_backup.task_class().validate_datetime(datetime.datetime(2026, 10, 18, 2, 30))
    assert not nightly_backup.task_class().validate_datetime(datetime.datetime(2026, 10, 18, 3, 30))
    with pytest.raises(ValueError):
        schedule_time("25:00")


# Restore command


@pytest.fixture
def backup_file(tmp_path):
    db = tmp_path / "source.sqlite3"
    make_database(db, rows=3).close()
    return archive.create_archive(db, tmp_path / "no-media", tmp_path / "backups", MOMENT)


@pytest.fixture
def restored(monkeypatch, tmp_path, settings):
    """Record what the restore command would write, instead of replacing the test database."""
    calls = {}
    monkeypatch.setattr(
        archive, "restore_database", lambda src, dst: calls.setdefault("db", count(src))
    )
    monkeypatch.setattr(archive, "restore_media", lambda src, dst: calls.setdefault("media", dst))
    settings.MEDIA_ROOT = tmp_path / "media"
    return calls


@pytest.mark.django_db
def test_restore_refuses_a_database_with_data_unless_forced(backup_file, restored, make_user):
    make_user("someone")

    with pytest.raises(CommandError, match="--force"):
        call_command("restore", str(backup_file))
    assert restored == {}

    call_command("restore", str(backup_file), "--force")
    assert restored["db"] == 3


@pytest.mark.django_db
def test_restore_into_a_fresh_database(backup_file, restored):
    call_command("restore", str(backup_file))

    assert restored["db"] == 3


@pytest.mark.django_db
def test_restore_downloads_from_the_remote(backup_file, restored, settings, monkeypatch):
    settings.BACKUP = dict(REMOTE, dir=backup_file.parent, keep=2, time="02:30")

    def download(self, name, destination):
        destination.write_bytes(backup_file.read_bytes())

    monkeypatch.setattr(Remote, "download", download)
    call_command("restore", backup_file.name, "--remote")

    assert restored["db"] == 3


@pytest.mark.django_db
def test_restore_reports_a_missing_file(restored):
    with pytest.raises(CommandError, match="does not exist"):
        call_command("restore", "/nowhere/metra-backup-x.tar.gz")


# Status panel


@pytest.mark.django_db
def test_admins_see_the_backup_status(role_client):
    BackupRun.objects.create(
        success=True,
        archive_name="a",
        size=2048,
        target="/data/backups",
        finished_at=timezone.now(),
    )

    page = role_client("Admin").get(reverse("register:unit_list"), HTTP_ACCEPT_LANGUAGE="en")

    html = page.content.decode()
    assert "Last successful backup" in html
    assert "/data/backups" in html


@pytest.mark.django_db
def test_failed_and_missing_backups_are_shown(role_client):
    client = role_client("Admin")
    assert (
        "Ingen säkerhetskopia har gjorts ännu."
        in client.get(reverse("register:unit_list")).content.decode()
    )

    BackupRun.objects.create(success=False, error="disk full", finished_at=timezone.now())
    html = client.get(reverse("register:unit_list"), HTTP_ACCEPT_LANGUAGE="en").content.decode()
    assert "The last backup failed" in html and "disk full" in html


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["Board", "Treasurer", "Read-only"])
def test_other_roles_do_not_see_backups(role_client, role):
    html = role_client(role).get(reverse("register:unit_list")).content.decode()

    assert 'id="backup-status"' not in html
