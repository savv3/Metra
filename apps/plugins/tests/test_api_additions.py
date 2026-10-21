"""PDFs, message drafts and the member page, as plugins use them through the API."""

import re
import sys

import pytest
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.test import RequestFactory
from django.urls import reverse

from apps.messaging.models import Attachment
from apps.plugins import api
from apps.plugins.hooks import MEMBER_PANELS, hooks
from apps.register.models import UnitContact
from apps.selfservice.models import SelfServiceLink

PDF = b"%PDF-1.4 notice"


# PDFs.


def test_render_pdf_makes_a_pdf():
    try:
        pdf = api.render_pdf("<h1>Hej</h1>")
    except api.PDFUnavailable:
        pytest.skip("WeasyPrint's Pango library is not installed here")

    assert pdf.startswith(b"%PDF")


def test_render_pdf_says_when_weasyprint_is_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "weasyprint", None)  # import fails

    with pytest.raises(api.PDFUnavailable):
        api.render_pdf("<h1>Hej</h1>")


# Message drafts.


def draft_for(client, user, **kwargs):
    """Make a draft in the logged-in client's session, as a plugin view would."""
    request = RequestFactory().get("/")
    request.user = user
    request.session = client.session
    url = api.message_draft(request, **kwargs)
    request.session.save()
    return url


@pytest.fixture
def admin(client, make_user):
    user = make_user("admin", "Admin")
    client.force_login(user)
    client.user = user
    return client


def test_message_draft_opens_the_new_message_form_filled_in(admin):
    url = draft_for(
        admin,
        admin.user,
        subject="Kallelse till årsmöte",
        body="Välkommen till årsmötet.",
        email_body="Hej {first_name}, välkommen.",
        files=[("Kallelse.pdf", PDF, "application/pdf")],
    )

    assert url.startswith(reverse("messaging:compose") + "?draft=")
    page = admin.get(url).content.decode()
    assert 'value="Kallelse till årsmöte"' in page
    assert "Välkommen till årsmötet." in page
    assert "Hej {first_name}, välkommen." in page
    attachment = Attachment.objects.get()
    assert attachment.uploaded_by == admin.user and attachment.batch is None
    assert re.search(rf'name="attachments" value="{attachment.pk}"[^>]*checked', page)
    with attachment.file.open("rb") as file:
        assert file.read() == PDF


def test_a_draft_is_only_for_the_user_who_made_it(admin, client, make_user):
    url = draft_for(admin, admin.user, subject="Hej", body="Hej", files=[("a.pdf", PDF, "")])
    other = make_user("other", "Admin")
    admin.force_login(other)  # a new session

    page = admin.get(url).content.decode()

    assert 'value="Hej"' not in page
    assert 'name="attachments"' not in page


def test_message_draft_refuses_files_that_cannot_be_attached(admin):
    with pytest.raises(ValidationError):
        draft_for(admin, admin.user, subject="x", body="x", files=[("run.exe", b"MZ", "")])
    assert not Attachment.objects.exists()


def test_an_unknown_draft_opens_an_empty_form(admin):
    response = admin.get(reverse("messaging:compose") + "?draft=nope")

    assert response.status_code == 200


# The member page.


@pytest.fixture
def member(unit, person):
    cache.clear()  # the member pages' rate limit
    UnitContact.objects.create(unit=unit, person=person, role=UnitContact.Role.OWNER)
    _link, token = SelfServiceLink.create_for(unit, person)
    yield token
    cache.clear()


@pytest.fixture
def panel():
    def context(request, member_link):
        return {"greeting": f"{member_link.person.first_name} of {member_link.unit.name}"}

    panel = api.MemberPanel("plugins_test/member_panel.html", "Extra", context)
    api.add_member_panel(panel)
    yield panel
    hooks._items[MEMBER_PANELS].remove(panel)


@pytest.fixture
def panel_template(settings, tmp_path):
    folder = tmp_path / "templates" / "plugins_test"
    folder.mkdir(parents=True)
    (folder / "member_panel.html").write_text(
        "<section><h2>{{ title }}</h2><p>{{ greeting }} ({{ token|length }})</p></section>"
    )
    settings.TEMPLATES = [
        {**settings.TEMPLATES[0], "DIRS": [*settings.TEMPLATES[0]["DIRS"], tmp_path / "templates"]}
    ]


def test_member_panels_show_on_the_member_page(client, member, panel, panel_template):
    page = client.get(f"/m/{member}/").content.decode()

    assert "<h2>Extra</h2>" in page
    assert f"Anna of Byvägen 4 ({len(member)})" in page


def test_a_failing_member_panel_does_not_break_the_member_page(client, member, settings):
    broken = api.MemberPanel("does/not/exist.html", "Broken")
    api.add_member_panel(broken)
    settings.DEBUG = False
    try:
        response = client.get(f"/m/{member}/", HTTP_ACCEPT_LANGUAGE="en")
    finally:
        hooks._items[MEMBER_PANELS].remove(broken)

    assert response.status_code == 200
    assert "Hello Anna" in response.content.decode()


def test_member_link_finds_the_member_behind_a_token(rf, member, unit, person):
    link = api.member_link(rf.get("/"), member)

    assert (link.unit, link.person, link.token) == (unit, person, member)


def test_a_bad_token_counts_as_a_failure(rf, member):
    request = rf.get("/")
    for _try in range(10):
        assert api.member_link(request, "not-a-token") is None

    # Too many failures: even the right token is refused for a while.
    assert api.member_link(request, member) is None
    response = api.member_unavailable(request)
    assert response.status_code == 429
    assert response["Referrer-Policy"] == "same-origin"


def test_member_response_is_private(member):
    response = api.member_response(HttpResponse(b"x"))

    assert "no-store" in response["Cache-Control"]
    assert response["X-Robots-Tag"] == "noindex, nofollow"
    assert api.member_page_url(member) == f"https://register.example.com/m/{member}/"
