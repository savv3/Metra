"""The notification service, the bell and the Notifications page."""

import datetime

import pytest
from django.db import transaction
from django.urls import reverse
from django.utils import timezone, translation

from apps.notifications import kinds, service
from apps.notifications.models import Notification, Preference, Recipient
from apps.notifications.service import notify
from apps.plugins import api
from apps.plugins.hooks import NOTIFICATION_KINDS, hooks

pytestmark = pytest.mark.django_db


@pytest.fixture
def sent(django_capture_on_commit_callbacks):
    """Run notify() and send what it queued for after the commit."""

    def send(*args, **kwargs):
        with django_capture_on_commit_callbacks(execute=True):
            notify(*args, **kwargs)

    return send


def copies(user):
    return Recipient.objects.filter(user=user)


def failed_backup(sent):
    sent("backup_failed", {"error": "disk full"}, link=reverse("backups:list"))


# Sending


def test_a_role_reaches_its_active_users_with_the_permission(sent, make_user):
    admin, other_admin = make_user("a", "Admin"), make_user("b", "Admin")
    gone = make_user("c", "Admin", is_active=False)
    board = make_user("d", "Board")

    failed_backup(sent)

    notification = Notification.objects.get()
    assert set(notification.recipients.values_list("user__username", flat=True)) == {"a", "b"}
    assert not copies(gone).exists() and not copies(board).exists()
    assert admin.notifications.count() == other_admin.notifications.count() == 1


def test_named_users_need_the_kinds_permission_too(sent, make_user):
    treasurer = make_user("t", "Treasurer")
    reader = make_user("r", "Read-only")

    sent("invoices_overdue", {"count": 2}, users=[treasurer, reader])

    assert copies(treasurer).exists()
    assert not copies(reader).exists()


def test_a_user_who_turned_a_kind_off_does_not_get_it(sent, make_user):
    keeps, quiet = make_user("keeps", "Admin"), make_user("quiet", "Admin")
    Preference.objects.create(user=quiet, kind="backup_failed", enabled=False)

    failed_backup(sent)

    assert copies(keeps).exists() and not copies(quiet).exists()


def test_a_kind_that_is_off_by_default_needs_opting_in(sent, make_user):
    opted_in, other = make_user("in", "Admin"), make_user("other", "Admin")
    Preference.objects.create(user=opted_in, kind="backup_done", enabled=True)

    sent("backup_done")

    assert copies(opted_in).exists() and not copies(other).exists()


def test_nothing_is_sent_when_the_change_is_rolled_back(
    make_user, django_capture_on_commit_callbacks
):
    make_user("a", "Admin")

    with django_capture_on_commit_callbacks(execute=True):
        try:
            with transaction.atomic():
                notify("backup_failed", {"error": "x"})
                raise RuntimeError("undo")
        except RuntimeError:
            pass

    assert not Notification.objects.exists()


def test_notify_never_raises(make_user, sent, monkeypatch):
    make_user("a", "Admin")

    def broken(*args, **kwargs):
        raise RuntimeError("database gone")

    monkeypatch.setattr(service, "send_now", broken)
    sent("backup_failed", {"error": "x"})  # no exception
    sent("no_such_kind")

    assert not Notification.objects.exists()


def test_grouping_updates_the_notification_and_makes_it_unread_again(sent, make_user):
    admin = make_user("a", "Admin")
    make_user("b", "Admin")  # b has not read it, so the group is still open
    sent("messages_failed", {"count": 2}, roles=["Admin"], group="batch-1")
    copy = copies(admin).get()
    copy.read_at = timezone.now()
    copy.save()

    sent("messages_failed", {"count": 1}, roles=["Admin"], group="batch-1")

    notification = Notification.objects.get()
    assert notification.params["count"] == 3
    copy.refresh_from_db()
    assert copy.read_at is None
    assert notification.recipients.count() == 2


def test_a_group_is_not_joined_once_everyone_read_it_or_after_a_day(sent, make_user):
    admin = make_user("a", "Admin")
    sent("messages_failed", {"count": 1}, roles=["Admin"], group="batch-1")
    copies(admin).update(read_at=timezone.now())

    sent("messages_failed", {"count": 1}, roles=["Admin"], group="batch-1")
    Notification.objects.update(created_at=timezone.now() - datetime.timedelta(days=2))
    sent("messages_failed", {"count": 1}, roles=["Admin"], group="batch-1")

    assert Notification.objects.count() == 3


# Text


def test_the_text_is_in_the_readers_language(sent, make_user):
    make_user("a", "Admin")
    sent("invoices_overdue", {"count": 3})
    notification = Notification.objects.get()

    with translation.override("en"):
        english = notification.text()
    with translation.override("sv"):
        swedish = notification.text()

    assert english == "3 invoices became overdue."
    assert swedish != english and "3" in swedish


def test_unknown_kinds_and_missing_details_do_not_crash(make_user):
    gone = Notification.objects.create(kind="removed_plugin_thing", params={"x": 1})
    odd = Notification.objects.create(kind="backup_failed", params={})
    broken = Notification.objects.create(kind="invoices_overdue", params=[1, 2])

    with translation.override("en"):
        assert "no longer installed" in gone.text()
        assert odd.text() == "A snapshot failed"
        assert broken.text() == "Invoices became overdue"


def test_variants_change_the_text(make_user):
    offsite = Notification.objects.create(
        kind="backup_failed", params={"error": "timeout", "variant": "offsite"}
    )

    with translation.override("en"):
        assert offsite.text() == "A snapshot could not be sent offsite: timeout"


# The bell and the page


def test_the_bell_shows_the_unread_count(client, make_user, sent):
    admin = make_user("a", "Admin")
    client.force_login(admin)
    for _ in range(3):
        failed_backup(sent)

    page = client.get(reverse("help:index"), HTTP_ACCEPT_LANGUAGE="en").content.decode()

    assert 'aria-label="Notifications, 3 unread"' in page
    assert '<span class="bell__count" aria-hidden="true">3</span>' in page


def test_the_bell_caps_the_number(client, make_user):
    admin = make_user("a", "Admin")
    client.force_login(admin)
    for _ in range(100):
        Recipient.objects.create(notification=Notification.objects.create(kind="x"), user=admin)

    page = client.get(reverse("help:index")).content.decode()

    assert ">99+</span>" in page


def test_no_bell_without_login_and_no_badge_without_unread(client, make_user):
    assert 'class="bell' not in client.get(reverse("account_login")).content.decode()
    client.force_login(make_user("a", "Admin"))

    page = client.get(reverse("help:index"), HTTP_ACCEPT_LANGUAGE="en").content.decode()

    assert 'class="bell"' in page and 'aria-label="Notifications"' in page
    assert "bell__count" not in page


def make_copy(user, kind="backup_failed", link="/backups/", minutes_ago=0, **params):
    moment = timezone.now() - datetime.timedelta(minutes=minutes_ago)
    notification = Notification.objects.create(
        kind=kind,
        params=params or {"error": "disk full"},
        link=link,
        created_at=moment,
        updated_at=moment,
    )
    return Recipient.objects.create(notification=notification, user=user)


@pytest.fixture
def admin(client, make_user):
    user = make_user("a", "Admin")
    client.force_login(user)
    return user


def test_the_list_is_newest_first_and_filters_unread(client, admin):
    old = make_copy(admin, minutes_ago=60, error="old one")
    make_copy(admin, error="new one")
    old.read_at = timezone.now()
    old.save()

    page = client.get(reverse("notifications:list"), HTTP_ACCEPT_LANGUAGE="en").content.decode()
    unread = client.get(reverse("notifications:list") + "?show=unread").content.decode()

    assert page.index("new one") < page.index("old one")
    assert "new one" in unread and "old one" not in unread
    assert "A snapshot failed: new one" in page  # in the reader's language


def test_opening_marks_read_and_follows_the_link(client, admin):
    copy = make_copy(admin)

    response = client.post(reverse("notifications:open", args=[copy.notification.pk]))

    assert response.status_code == 302 and response.url == "/backups/"
    copy.refresh_from_db()
    assert copy.read_at is not None


@pytest.mark.parametrize(
    "link", ["https://evil.example.com/", "//evil.example.com/", "javascript:alert(1)"]
)
def test_links_to_other_sites_are_never_followed(client, admin, link):
    copy = make_copy(admin, link=link)

    response = client.post(reverse("notifications:open", args=[copy.notification.pk]))

    assert response.url == reverse("notifications:list")


def test_actions_never_redirect_to_other_sites(client, admin):
    copy = make_copy(admin)

    response = client.post(
        reverse("notifications:read", args=[copy.notification.pk]),
        {"next": "https://evil.example.com/"},
    )

    assert response.url == reverse("notifications:list")


def test_marking_read_unread_and_dismissing(client, admin):
    copy = make_copy(admin)
    pk = copy.notification.pk

    client.post(reverse("notifications:read", args=[pk]), {"next": "/notifications/?show=unread"})
    copy.refresh_from_db()
    assert copy.read_at is not None
    client.post(reverse("notifications:unread", args=[pk]))
    copy.refresh_from_db()
    assert copy.read_at is None

    response = client.post(reverse("notifications:dismiss", args=[pk]), follow=True)

    copy.refresh_from_db()
    assert copy.dismissed_at is not None
    assert copy.notification.text() not in response.content.decode()


def test_mark_all_as_read(client, admin):
    make_copy(admin)
    make_copy(admin)

    client.post(reverse("notifications:read_all"))

    assert not copies(admin).filter(read_at__isnull=True).exists()


def test_changes_need_post(client, admin):
    copy = make_copy(admin)

    assert (
        client.get(reverse("notifications:dismiss", args=[copy.notification.pk])).status_code == 405
    )


def test_nobody_sees_or_touches_anothers_notifications(client, admin, make_user):
    other = make_user("b", "Admin")
    theirs = make_copy(other, error="theirs only")
    pk = theirs.notification.pk

    page = client.get(reverse("notifications:list")).content.decode()
    client.post(reverse("notifications:read_all"))
    statuses = [
        client.post(reverse(f"notifications:{action}", args=[pk])).status_code
        for action in ["open", "read", "unread", "dismiss"]
    ]

    assert "theirs only" not in page
    assert statuses == [404, 404, 404, 404]
    theirs.refresh_from_db()
    assert theirs.read_at is None and theirs.dismissed_at is None


def test_the_page_needs_a_login(client):
    response = client.get(reverse("notifications:list"))

    assert response.status_code == 302 and "/accounts/login/" in response.url


# Settings


def test_settings_list_only_kinds_the_user_may_get_and_save_choices(client, make_user):
    treasurer = make_user("t", "Treasurer")
    client.force_login(treasurer)

    page = client.get(reverse("notifications:settings"), HTTP_ACCEPT_LANGUAGE="en")
    client.post(reverse("notifications:settings"), {"kinds": ["backup_failed"]})

    text = page.content.decode()
    assert 'value="invoices_overdue" checked' in text
    assert 'value="backup_failed"' not in text
    choices = dict(Preference.objects.filter(user=treasurer).values_list("kind", "enabled"))
    assert choices["invoices_overdue"] is False
    assert "backup_failed" not in choices


def test_admins_can_opt_in_to_the_nightly_snapshot(client, admin):
    page = client.get(reverse("notifications:settings")).content.decode()
    assert 'value="backup_done">' in page

    client.post(reverse("notifications:settings"), {"kinds": ["backup_done", "backup_failed"]})

    choices = dict(Preference.objects.filter(user=admin).values_list("kind", "enabled"))
    assert choices["backup_done"] and choices["backup_failed"]
    assert not choices["restore_done"]


# Cleanup


def test_cleanup_removes_only_old_read_or_dismissed_copies(admin, make_user):
    long_ago = timezone.now() - datetime.timedelta(days=91)
    recently = timezone.now() - datetime.timedelta(days=89)
    old_read = make_copy(admin)
    Recipient.objects.filter(pk=old_read.pk).update(read_at=long_ago)
    old_dismissed = make_copy(admin)
    Recipient.objects.filter(pk=old_dismissed.pk).update(dismissed_at=long_ago)
    recent = make_copy(admin)
    Recipient.objects.filter(pk=recent.pk).update(read_at=recently)
    unread = make_copy(admin, minutes_ago=200 * 24 * 60)
    Notification.objects.update(updated_at=long_ago)

    assert service.delete_old() == 2

    assert set(Recipient.objects.values_list("pk", flat=True)) == {recent.pk, unread.pk}
    assert Notification.objects.count() == 2


# Plugins


@pytest.fixture
def plugin_kind():
    kind = api.NotificationKind(
        "thing_failed", "A thing failed", "%(thing)s failed.", roles=["Board"]
    )
    api.add_notification_kind(kind)
    yield kind
    hooks._items[NOTIFICATION_KINDS].remove(kind)


def test_a_plugin_registers_and_sends_its_own_kind(
    plugin_kind, make_user, django_capture_on_commit_callbacks
):
    board = make_user("b", "Board")

    with django_capture_on_commit_callbacks(execute=True):
        api.notify("thing_failed", {"thing": "The pump"}, link="/")

    assert kinds.get("thing_failed") is plugin_kind
    assert copies(board).get().notification.text() == "The pump failed."


def test_a_plugin_cannot_replace_a_core_kind():
    impostor = api.NotificationKind("backup_failed", "Mine", "Mine", roles=["Board"])
    api.add_notification_kind(impostor)
    try:
        assert kinds.get("backup_failed") is not impostor
    finally:
        hooks._items[NOTIFICATION_KINDS].remove(impostor)
