import datetime
import re
from decimal import Decimal as D

from auditlog.models import LogEntry
from django.utils import timezone

from apps.readings.models import Reading, ReadingRound
from apps.register.models import Person, UnitContact
from apps.selfservice import ratelimit
from apps.selfservice.models import SelfServiceLink

CSRF = re.compile(r'name="csrfmiddlewaretoken"[^>]*value="[^"]+"')


def test_member_page_opens_without_login(client, issued, unit):
    _link, _token, url = issued

    response = client.get(url, HTTP_ACCEPT_LANGUAGE="en")

    body = response.content.decode()
    assert response.status_code == 200
    assert "Hello Anna" in body
    assert "Byvägen 4" in body
    assert response["X-Robots-Tag"] == "noindex, nofollow"
    assert response["Referrer-Policy"] == "same-origin"
    assert "no-store" in response["Cache-Control"]
    assert '<meta name="robots" content="noindex, nofollow">' in body


def test_unknown_expired_and_revoked_links_look_the_same(client, issued, unit, owner):
    link, token, url = issued
    expired, expired_token = SelfServiceLink.create_for(
        unit, owner, expires_at=timezone.now() - datetime.timedelta(minutes=1)
    )

    unknown = client.get("/m/not-a-real-token/")
    old = client.get(f"/m/{expired_token}/")
    link.revoked = True
    link.save()
    revoked = client.get(url)

    assert unknown.status_code == old.status_code == revoked.status_code == 404
    pages = [CSRF.sub("", r.content.decode()) for r in (unknown, old, revoked)]
    assert pages[0] == pages[1] == pages[2]
    assert unknown["Referrer-Policy"] == "same-origin"


def test_visits_are_logged_and_last_opened_updated(client, issued):
    link, _token, url = issued

    client.get(url)

    link.refresh_from_db()
    assert link.last_used_at is not None
    view = LogEntry.objects.get_for_object(link).get(action=LogEntry.Action.ACCESS)
    assert view.additional_data["self_service_link"] == link.pk


def test_member_reports_reading(client, issued, unit, owner, open_round):
    link, _token, url = issued

    response = client.post(url, {"action": "reading", "value": "1234"})

    assert response.status_code == 302
    reading = Reading.objects.get()
    assert (reading.value, reading.source) == (D(1234), "member")
    assert reading.submitted_by is None
    assert reading.submitted_by_person == owner
    entry = LogEntry.objects.get_for_object(reading).get()
    assert entry.additional_data["self_service_link"] == link.pk
    assert entry.additional_data["unit_id"] == unit.pk
    assert entry.actor is None


def test_member_can_change_reading_while_round_is_open(client, issued):
    _link, _token, url = issued
    client.post(url, {"action": "reading", "value": "100"})

    client.post(url, {"action": "reading", "value": "101"})

    assert Reading.objects.get().value == 101


def test_reading_shows_previous_value_and_rejects_bad_input(client, issued, unit, meter):
    last = ReadingRound.objects.create(
        reading_type=meter,
        period_label="Last year",
        opens_on=datetime.date(2000, 1, 1),
        closes_on=datetime.date(2000, 12, 31),
        is_draft=False,
    )
    Reading.objects.create(round=last, unit=unit, value=900)
    _link, _token, url = issued

    page = client.get(url, HTTP_ACCEPT_LANGUAGE="en").content.decode()
    bad = client.post(url, {"action": "reading", "value": "-5"}, HTTP_ACCEPT_LANGUAGE="en")

    assert "Last time the reading was 900 m³" in page
    assert bad.status_code == 200
    assert 'role="alert"' in bad.content.decode()
    assert not Reading.objects.filter(round__period_label=str(timezone.localdate().year)).exists()


def test_closed_round_shows_the_reading_but_accepts_no_changes(client, issued, unit, open_round):
    _link, _token, url = issued
    Reading.objects.create(round=open_round, unit=unit, value=50)
    open_round.closes_on = timezone.localdate() - datetime.timedelta(days=1)
    open_round.save()

    page = client.get(url, HTTP_ACCEPT_LANGUAGE="en").content.decode()
    client.post(url, {"action": "reading", "value": "99"})

    assert "can no longer be changed" in page
    assert Reading.objects.get().value == 50


def test_member_corrects_own_contact_details(client, issued, owner):
    link, _token, url = issued

    client.post(
        url,
        {
            "action": "contact",
            "email": "anna.l@example.com",
            "phone": "+358 40 123",
            "street_address": "Byvägen 4",
            "postal_code": "22100",
            "city": "Mariehamn",
        },
    )

    owner.refresh_from_db()
    assert (owner.email, owner.phone, owner.postal_code) == (
        "anna.l@example.com",
        "+358 40 123",
        "22100",
    )
    entry = LogEntry.objects.get_for_object(owner).get(action=LogEntry.Action.UPDATE)
    assert entry.additional_data["self_service_link"] == link.pk
    assert entry.changes_dict["email"] == ["anna@example.com", "anna.l@example.com"]


def test_contact_form_keeps_the_preferred_channel_reachable(client, issued, owner):
    _link, _token, url = issued

    response = client.post(url, {"action": "contact", "email": "", "phone": ""})

    assert response.status_code == 200
    owner.refresh_from_db()
    assert owner.email == "anna@example.com"


def test_member_sees_household_but_cannot_edit_others(client, issued, unit, owner):
    partner = Person.objects.create(first_name="Erik", email="erik@example.com")
    UnitContact.objects.create(unit=unit, person=partner, role="contact")
    _link, _token, url = issued

    page = client.get(url, HTTP_ACCEPT_LANGUAGE="en").content.decode()
    client.post(url, {"action": "contact", "email": "changed@example.com", "person": partner.pk})

    assert "Erik" in page
    assert "erik@example.com" not in page  # names and roles only
    partner.refresh_from_db()
    assert partner.email == "erik@example.com"


def test_link_without_round_only_shows_contact_details(client, unit, owner):
    _link, token = SelfServiceLink.create_for(unit, owner)

    page = client.get(f"/m/{token}/", HTTP_ACCEPT_LANGUAGE="en").content.decode()

    assert "Your contact details" in page
    assert 'name="value"' not in page


def test_guessing_tokens_is_rate_limited(client, issued):
    _link, _token, url = issued
    for _ in range(ratelimit.FAILURES[0]):
        assert client.get("/m/guess/").status_code == 404

    blocked = client.get(url)

    assert blocked.status_code == 429


def test_too_many_visits_are_refused(client, issued, settings, monkeypatch):
    monkeypatch.setattr(ratelimit, "VISITS", (3, 600))
    _link, _token, url = issued

    statuses = [client.get(url).status_code for _ in range(4)]

    assert statuses == [200, 200, 200, 429]


def test_forwarded_address_is_used_only_when_trusted(rf, settings):
    request = rf.get("/", HTTP_X_FORWARDED_FOR="1.2.3.4, 5.6.7.8", REMOTE_ADDR="10.0.0.1")

    settings.TRUST_X_FORWARDED_FOR = False
    assert ratelimit.client_ip(request) == "10.0.0.1"
    settings.TRUST_X_FORWARDED_FOR = True
    assert ratelimit.client_ip(request) == "5.6.7.8"


def test_logged_in_staff_without_two_factor_can_open_member_pages(client, issued, make_user):
    _link, _token, url = issued
    client.force_login(make_user("admin", "Admin", is_staff=True))

    assert client.get(url).status_code == 200


def test_member_page_is_translated(client, issued):
    _link, _token, url = issued

    page = client.get(url, HTTP_ACCEPT_LANGUAGE="sv").content.decode()

    assert "Hej Anna" in page


def test_forms_need_a_csrf_token_and_pass_with_same_origin_headers(issued):
    from django.test import Client

    _link, _token, url = issued
    browser = Client(enforce_csrf_checks=True)
    page = browser.get(url)
    csrf = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page.content.decode())[1]

    refused = browser.post(
        url, {"action": "reading", "value": "4"}, HTTP_ORIGIN="http://testserver"
    )
    accepted = browser.post(
        url,
        {"action": "reading", "value": "5", "csrfmiddlewaretoken": csrf},
        HTTP_ORIGIN="http://testserver",
        HTTP_REFERER="http://testserver" + url,
    )

    assert refused.status_code == 403
    assert accepted.status_code == 302
    assert Reading.objects.get().value == 5


def test_language_links_set_the_language(client, issued):
    _link, _token, url = issued

    response = client.get(url + "?lang=en")
    page = client.get(url).content.decode()

    assert response.status_code == 302
    assert response.url == url
    assert "Hello Anna" in page
