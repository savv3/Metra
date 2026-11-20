"""Putting a demo site back to its made-up demo data (METRA_DEMO=true).

The reset empties the database and the uploads, migrates the empty database
and loads the demo association again, with the shared demo account. While it
runs, the site is in maintenance mode, so the web processes do not touch the
database it replaces. It refuses to run anywhere but on a demo site, so it can
never wipe a real install.
"""

import shutil
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.management import call_command
from django.db import connection, connections

from apps.backups import restore


class NotADemo(Exception):
    """METRA_DEMO is off: this install holds real data."""


def has_demo_account():
    from django.db.utils import OperationalError

    try:
        return User.objects.filter(username=settings.DEMO_USERNAME).exists()
    except OperationalError:
        return False  # not migrated yet


def reset(stdout=None):
    """Replace everything with fresh demo data. Raises NotADemo unless METRA_DEMO is on."""
    if not settings.DEMO:
        raise NotADemo("METRA_DEMO is off; this would delete real data.")
    restore.maintenance_path().write_text('{"demo_reset": true}')
    try:
        _empty_database()
        call_command("migrate", interactive=False, verbosity=0)
        # The new database numbers its content types afresh (the audit log
        # points at them); the web processes notice through the marker file.
        ContentType.objects.clear_cache()
        _empty_folder(settings.MEDIA_ROOT)
        _empty_folder(settings.BACKUP["dir"])
        cache.clear()
        call_command("load_demo_data", stdout=stdout)
        create_demo_account()
    finally:
        connections.close_all()
        reset_marker().touch()
        restore.maintenance_path().unlink(missing_ok=True)


def reset_marker():
    """A file touched after every reset, so each web process can forget what
    it cached from the database before it (see ``forget_old_database``)."""
    return Path(settings.DATA_DIR) / "demo-reset"


_seen_reset = None


def forget_old_database():
    """Clear this process's content type cache once after each reset."""
    global _seen_reset
    try:
        stamp = reset_marker().stat().st_mtime_ns
    except FileNotFoundError:
        return
    if stamp != _seen_reset:
        if _seen_reset is not None:
            ContentType.objects.clear_cache()
        _seen_reset = stamp


def create_demo_account():
    """The shared login everyone uses: an admin, so every page can be tried."""
    user = User.objects.create_user(
        settings.DEMO_USERNAME,
        password=settings.DEMO_PASSWORD,
        first_name="Demo",
        is_staff=True,
    )
    user.groups.add(Group.objects.get(name="Admin"))
    return user


def _empty_database():
    """Drop every table, so migrate builds the database as on a new install."""
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA foreign_keys = OFF")
        # Virtual tables first: dropping one drops its shadow tables too.
        cursor.execute(
            "SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view') "
            "AND name NOT LIKE 'sqlite_%' ORDER BY sql LIKE 'CREATE VIRTUAL%' DESC"
        )
        for name, kind in cursor.fetchall():
            statement = "VIEW" if kind == "view" else "TABLE"
            cursor.execute(f'DROP {statement} IF EXISTS "{name}"')
        cursor.execute("PRAGMA foreign_keys = ON")
    connection.close()
    with connection.cursor() as cursor:
        cursor.execute("VACUUM")


def _empty_folder(path):
    path = Path(path)
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
