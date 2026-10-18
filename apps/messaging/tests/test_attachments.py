import datetime
import re

import pytest
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.messaging import attachments, providers
from apps.messaging.models import Attachment, ConsentRecord, Message, MessageBatch
from apps.register.models import Person

URL = "/messages/new/"
PDF = b"%PDF-1.4 agenda"


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def agenda(name="Kallelse.pdf", content=PDF):
    return SimpleUploadedFile(name, content, content_type="application/pdf")


def post(client, url=URL, step="preview", **data):
    fields = {
        "scope": "everyone",
        "contacts": "all",
        "channels": "sms_and_email",
        "body": "Välkommen till årsmötet.",
        "subject": "Årsmöte",
        "step": step,
    }
    return client.post(url, {**fields, **data}, HTTP_ACCEPT_LANGUAGE="en")


def ids(page):
    return re.findall(r'name="attachments" value="(\d+)"', page)


def test_agenda_goes_by_email_and_as_a_link_by_sms(admin_client, make_household):
    make_household("A", first_name="Anna", phone="0401234567", email="anna@example.com")

    preview = post(admin_client, files=[agenda()]).content.decode()
    assert "Kallelse.pdf" in preview
    assert "SMS recipients get a link" in preview
    post(admin_client, step="confirm", attachments=ids(preview))

    batch = MessageBatch.objects.get()
    assert [a.name for a in batch.attachments.all()] == ["Kallelse.pdf"]
    email = mail.outbox[0]
    assert email.attachments == [("Kallelse.pdf", PDF, "application/pdf")]
    sms = providers.outbox[0]["body"]
    link = re.search(r"Files: (https://register\.example\.com/f/[\w-]+/)", sms).group(1)
    stored = batch.messages.get(channel="sms").body
    assert "[file link]" in stored and link not in stored

    path = link.removeprefix("https://register.example.com")
    page = admin_client.get(path, HTTP_ACCEPT_LANGUAGE="en").content.decode()
    assert "Kallelse.pdf" in page
    download = admin_client.get(f"{path}{batch.attachments.get().pk}/")
    assert download["Content-Disposition"].startswith("attachment")
    assert b"".join(download.streaming_content) == PDF


def test_the_file_link_needs_no_login_and_expires(client, admin_client, make_household):
    make_household("A", first_name="Anna", phone="0401234567")
    preview = post(admin_client, channels="sms", subject="", files=[agenda()]).content.decode()
    post(admin_client, step="confirm", channels="sms", subject="", attachments=ids(preview))
    path = re.search(r"/f/[\w-]+/", providers.outbox[0]["body"]).group(0)
    client.logout()

    assert client.get(path).status_code == 200
    MessageBatch.objects.update(files_expire_at=timezone.now() - datetime.timedelta(minutes=1))
    assert client.get(path).status_code == 404
    assert client.get(f"{path}{Attachment.objects.get().pk}/").status_code == 404
    assert client.get("/f/not-a-token/").status_code == 404


def test_sms_count_includes_the_link(admin_client, make_household):
    make_household("A", first_name="Anna", phone="0401234567")
    body = "x" * 150

    without = post(admin_client, channels="sms", subject="", body=body).context
    with_file = post(admin_client, channels="sms", subject="", body=body, files=[agenda()]).context

    assert without["sms_total"] == 1
    assert with_file["sms_total"] == 2


def test_files_are_checked_for_type_and_size(admin_client, settings):
    settings.MESSAGING = {**settings.MESSAGING, "attachment_file_mb": 1, "attachment_total_mb": 1}

    bad = post(admin_client, files=[agenda("run.exe", b"MZ")]).content.decode()
    big = post(admin_client, files=[agenda(content=b"x" * (1024 * 1024 + 1))]).content.decode()
    two = post(
        admin_client, files=[agenda("a.pdf", b"x" * 600_000), agenda("b.pdf", b"x" * 600_000)]
    ).content.decode()

    assert "run.exe: this kind of file cannot be attached." in bad
    assert "is larger than 1.0" in big
    assert "at most 1.0" in two
    assert not Attachment.objects.exists()


def test_going_back_keeps_files_and_unticking_drops_one(admin_client, make_household):
    make_household("A", first_name="Anna", email="anna@example.com")
    preview = post(admin_client, files=[agenda("a.pdf"), agenda("b.pdf")]).content.decode()
    kept = ids(preview)

    edit = post(admin_client, step="confirm", edit="1", attachments=kept).content.decode()
    assert "a.pdf" in edit and "b.pdf" in edit

    post(admin_client, step="confirm", attachments=kept[:1])

    assert [a.name for a in MessageBatch.objects.get().attachments.all()] == ["a.pdf"]
    assert [name for name, _content, _type in mail.outbox[0].attachments] == ["a.pdf"]


def test_nobody_can_send_another_users_files(admin_client, make_user, make_household):
    make_household("A", first_name="Anna", email="anna@example.com")
    other = Attachment.objects.create(
        name="other.pdf", size=3, content_type="application/pdf", uploaded_by=make_user("x")
    )

    response = post(admin_client, step="confirm", channels="email", attachments=[other.pk])

    assert response.status_code == 200  # the form again, with an error
    assert not MessageBatch.objects.exists()
    assert mail.outbox == []


def test_newsletter_attachments(admin_client):
    reader = Person.objects.create(first_name="Anna", email="anna@example.com")
    ConsentRecord.record(reader, True, ConsentRecord.Source.STAFF)
    url = reverse("messaging:newsletter_compose")
    data = {"subject": "Nyheter", "body": "Hej {first_name}"}

    preview = admin_client.post(url, {**data, "step": "preview", "files": [agenda()]})
    admin_client.post(
        url, {**data, "step": "confirm", "attachments": ids(preview.content.decode())}
    )

    assert [name for name, _c, _t in mail.outbox[0].attachments] == ["Kallelse.pdf"]


def test_staff_download_needs_the_permission(
    admin_client, role_client, make_household, make_user, client
):
    make_household("A", first_name="Anna", email="anna@example.com")
    preview = post(admin_client, files=[agenda()]).content.decode()
    post(admin_client, step="confirm", attachments=ids(preview))
    batch = MessageBatch.objects.get()
    url = reverse("messaging:attachment_download", args=[batch.pk, batch.attachments.get().pk])

    assert url in admin_client.get(batch.get_absolute_url()).content.decode()
    assert admin_client.get(url).status_code == 200
    assert role_client("Board").get(url).status_code == 200  # Board may view send-outs
    client.force_login(make_user("nobody"))
    assert client.get(url).status_code == 403


def test_unsent_files_are_removed_after_a_day(admin_client, tmp_path):
    post(admin_client, files=[agenda()])
    attachment = Attachment.objects.get()
    path = attachment.file.path

    attachments.remove_unsent()
    assert Attachment.objects.exists()

    Attachment.objects.update(uploaded_at=timezone.now() - datetime.timedelta(days=2))
    attachments.remove_unsent()

    assert not Attachment.objects.exists()
    assert not (tmp_path / path).exists()


def test_files_are_stored_under_the_data_dir(admin_client, tmp_path):
    post(admin_client, files=[agenda()])

    assert Attachment.objects.get().file.path.startswith(str(tmp_path / "attachments"))


def test_a_provider_without_attachments_fails_cleanly(admin_client, make_household, monkeypatch):
    from apps.messaging.providers import DjangoEmail

    def send(self, recipient, body, subject="", callback_url=None):
        raise AssertionError("not called")

    monkeypatch.setattr(DjangoEmail, "send", send)
    make_household("A", first_name="Anna", email="anna@example.com")
    preview = post(admin_client, channels="email", files=[agenda()]).content.decode()
    post(admin_client, step="confirm", channels="email", attachments=ids(preview))

    message = Message.objects.get()
    assert message.status == "failed"
    assert "cannot send attachments" in message.error
