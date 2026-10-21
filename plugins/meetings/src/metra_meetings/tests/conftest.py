import datetime

import pytest
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

from apps.plugins import api
from metra_meetings.models import AgendaItem, Meeting

PDF = b"%PDF-1.4 meeting"


@pytest.fixture(autouse=True)
def clear_cache():
    """The member pages' rate limit lives in the cache."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def login(make_user, settings):
    """A logged-in client for a new user with a role, seeing English pages."""

    def make(username, role=None):
        client = Client()
        client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"
        user = make_user(username, role)
        client.force_login(user)
        client.user = user
        return client

    return make


@pytest.fixture
def admin(login):
    return login("admin", "Admin")


@pytest.fixture
def make_household(household):
    def make(name, **person):
        unit = api.Unit.objects.create(unit_type=household, name=name)
        contact = api.Person.objects.create(**person)
        api.UnitContact.objects.create(unit=unit, person=contact, role="owner")
        return unit, contact

    return make


@pytest.fixture
def meeting(db):
    meeting = Meeting.objects.create(
        title="Annual meeting 2026",
        starts_at=timezone.make_aware(datetime.datetime(2026, 4, 20, 18, 30)),
        place="Village hall",
    )
    AgendaItem.objects.create(meeting=meeting, order=1, title="Opening of the meeting")
    AgendaItem.objects.create(
        meeting=meeting, order=2, title="Accounts for 2025", description="The board presents."
    )
    return meeting


@pytest.fixture
def fake_pdf(monkeypatch):
    """PDFs without WeasyPrint, for tests about where they go."""
    from metra_meetings import documents

    monkeypatch.setattr(documents, "agenda_pdf", lambda meeting: PDF)
    monkeypatch.setattr(documents, "minutes_pdf", lambda meeting: PDF)
    return PDF


def weasyprint_or_skip():
    try:
        api.render_pdf("<p>x</p>")
    except api.PDFUnavailable:
        pytest.skip("WeasyPrint's Pango library is not installed here")
