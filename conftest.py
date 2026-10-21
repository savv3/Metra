import sqlite3

import pytest
from django.contrib.auth.models import Group

from apps.register.models import CustomField, Person, Unit, UnitType


@pytest.fixture
def make_user(db, django_user_model):
    """Create a user with one of the roles (Admin, Board, Treasurer, Read-only)."""

    def make(username, role=None, **extra):
        user = django_user_model.objects.create_user(username, password="pw", **extra)
        if role:
            user.groups.add(Group.objects.get(name=role))
        return user

    return make


@pytest.fixture
def role_client(client, make_user):
    """Log the test client in as a user with the given role."""

    def login(role):
        client.force_login(make_user(role.lower(), role))
        return client

    return login


@pytest.fixture
def board_client(role_client):
    return role_client("Board")


@pytest.fixture
def household(db):
    unit_type = UnitType.objects.create(name="Household")
    CustomField.objects.create(
        target=CustomField.Target.UNIT,
        unit_type=unit_type,
        key="meter_number",
        label="Meter number",
        required=True,
    )
    CustomField.objects.create(
        target=CustomField.Target.UNIT,
        unit_type=unit_type,
        key="connected",
        label="Connected since",
        field_type=CustomField.FieldType.DATE,
        order=1,
    )
    CustomField.objects.create(
        target=CustomField.Target.UNIT,
        unit_type=unit_type,
        key="usage_limit",
        label="Usage limit",
        field_type=CustomField.FieldType.NUMBER,
        order=2,
    )
    return unit_type


@pytest.fixture
def unit(household):
    return Unit.objects.create(
        unit_type=household,
        name="Byvägen 4",
        street_address="Byvägen 4",
        city="Mariehamn",
        custom_data={"meter_number": "M-100"},
    )


@pytest.fixture
def person(db):
    return Person.objects.create(first_name="Anna", last_name="Lindqvist", email="anna@example.com")


@pytest.fixture(autouse=True)
def plugin_states():
    """Every test starts with the plugins' on/off states read afresh."""
    from apps.plugins import state

    state.forget()
    yield
    state.forget()


@pytest.fixture(autouse=True)
def snapshots_in_tmp(settings, tmp_path, monkeypatch):
    """Snapshots and restores during a test (before an import, a deletion or a
    restore) use a small throwaway database and a temporary data folder."""
    source = tmp_path / "snapshot-source.sqlite3"
    sqlite3.connect(source).close()
    monkeypatch.setattr("apps.backups.service.database_path", lambda: source)
    settings.BACKUP = {**settings.BACKUP, "dir": tmp_path / "snapshots", "remote_type": ""}
    # Restores replace the media folder and write files into the data folder:
    # never the real ones.
    settings.DATA_DIR = tmp_path
    settings.MEDIA_ROOT = tmp_path / "media"
