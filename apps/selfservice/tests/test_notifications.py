"""What members send in through their links shows up under the bell."""

from django.urls import reverse

from apps.notifications.models import Notification, Recipient

CONTACT = {
    "action": "contact",
    "email": "anna.l@example.com",
    "phone": "+358 40 123",
    "street_address": "Byvägen 4",
    "postal_code": "22100",
    "city": "Mariehamn",
}


def test_readings_and_contact_changes_notify_the_board_once_a_day(
    client, issued, make_user, django_capture_on_commit_callbacks
):
    board, admin = make_user("board", "Board"), make_user("admin", "Admin")
    treasurer = make_user("treasurer", "Treasurer")
    _link, _token, url = issued

    with django_capture_on_commit_callbacks(execute=True):
        client.post(url, {"action": "reading", "value": "1234"})
    with django_capture_on_commit_callbacks(execute=True):
        client.post(url, CONTACT)
    with django_capture_on_commit_callbacks(execute=True):
        client.post(url, {"action": "newsletter", "subscribed": "1"})

    notification = Notification.objects.get(kind="self_service_change")
    assert notification.params["count"] == 3
    assert notification.link == reverse("selfservice:recent_changes")
    assert "Anna" not in str(notification.params)
    users = set(notification.recipients.values_list("user", flat=True))
    assert users == {board.pk, admin.pk}
    assert not Recipient.objects.filter(user=treasurer).exists()


def test_an_unchanged_contact_form_notifies_nobody(
    client, issued, owner, make_user, django_capture_on_commit_callbacks
):
    make_user("board", "Board")
    _link, _token, url = issued
    same = {
        "action": "contact",
        "email": owner.email,
        "phone": owner.phone,
        "street_address": owner.street_address,
        "postal_code": owner.postal_code,
        "city": owner.city,
    }

    with django_capture_on_commit_callbacks(execute=True):
        client.post(url, same)

    assert not Notification.objects.exists()
