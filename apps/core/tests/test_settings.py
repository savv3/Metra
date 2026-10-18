import pytest
from django.db import connection


@pytest.mark.django_db
def test_sqlite_enforces_foreign_keys():
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA foreign_keys")
        assert cursor.fetchone()[0] == 1
