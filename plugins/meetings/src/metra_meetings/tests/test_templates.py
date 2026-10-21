import pytest
from django.urls import reverse

from metra_meetings import defaults
from metra_meetings.models import AgendaTemplate, Meeting


def url(name, *args):
    return reverse(f"metra_meetings:{name}", args=args)


NEW_MEETING = {"kind": "annual", "title": "Annual meeting", "starts_at": "2026-04-20T18:30"}


@pytest.fixture
def templates(db):
    AgendaTemplate.objects.all().delete()
    annual = AgendaTemplate.objects.create(
        name="Annual", kind="annual", items="Opening\n\n  Election of a chair  \nClosing\n"
    )
    spare = AgendaTemplate.objects.create(name="Spring cleaning", items="Tools\nCoffee")
    return annual, spare


def titles(meeting):
    return list(meeting.items.values_list("order", "title"))


def test_installations_start_with_the_usual_templates(db):
    assert set(AgendaTemplate.objects.values_list("kind", flat=True)) == {"annual", "board"}


def test_default_templates_are_in_the_chosen_language(db):
    AgendaTemplate.objects.all().delete()

    defaults.create(AgendaTemplate, language="en")
    defaults.create(AgendaTemplate, language="en")  # only once

    annual = AgendaTemplate.objects.get(kind="annual")
    assert annual.name == "Annual meeting"
    assert annual.titles()[0] == "Opening of the meeting"
    assert AgendaTemplate.objects.count() == 2


def test_a_new_meeting_starts_with_the_template_for_its_kind(login, templates):
    board = login("board", "Board")

    response = board.post(url("meeting_create"), {**NEW_MEETING, "agenda": "auto"}, follow=True)

    meeting = Meeting.objects.get()
    assert titles(meeting) == [(1, "Opening"), (2, "Election of a chair"), (3, "Closing")]
    assert "with the agenda from Annual" in response.content.decode()


def test_a_kind_without_a_template_starts_empty(login, templates):
    board = login("board", "Board")

    board.post(url("meeting_create"), {**NEW_MEETING, "kind": "board", "agenda": "auto"})

    assert titles(Meeting.objects.get()) == []


def test_any_template_or_none_can_be_chosen(login, templates):
    board = login("board", "Board")
    _annual, spare = templates

    board.post(url("meeting_create"), {**NEW_MEETING, "agenda": str(spare.pk)})
    board.post(url("meeting_create"), {**NEW_MEETING, "title": "Bare", "agenda": "empty"})

    assert titles(Meeting.objects.get(title="Annual meeting")) == [(1, "Tools"), (2, "Coffee")]
    assert titles(Meeting.objects.get(title="Bare")) == []


def test_the_choice_is_only_on_new_meetings(login, templates, meeting):
    board = login("board", "Board")

    assert 'name="agenda"' in board.get(url("meeting_create")).content.decode()
    assert 'name="agenda"' not in board.get(url("meeting_edit", meeting.pk)).content.decode()


def test_board_edits_templates_and_admins_delete_them(login, admin, templates):
    board = login("board", "Board")
    annual, _spare = templates

    page = board.get(url("template_list")).content.decode()
    assert "Spring cleaning" in page and url("template_edit", annual.pk) in page

    board.post(url("template_create"), {"name": "Extra", "kind": "extraordinary", "items": "A"})
    board.post(
        url("template_edit", annual.pk), {"name": "Annual", "kind": "annual", "items": "Hello"}
    )
    assert board.post(url("template_delete", annual.pk)).status_code == 403
    admin.post(url("template_delete", annual.pk))

    assert AgendaTemplate.objects.get(name="Extra").kind == "extraordinary"
    assert not AgendaTemplate.objects.filter(pk=annual.pk).exists()


def test_one_template_per_kind(login, templates):
    board = login("board", "Board")

    response = board.post(url("template_create"), {"name": "Other", "kind": "annual", "items": "A"})

    assert response.status_code == 200
    assert "Another template is already used for this kind of meeting." in response.content.decode()


def test_changing_a_template_leaves_meetings_alone(login, templates):
    board = login("board", "Board")
    annual, _spare = templates
    board.post(url("meeting_create"), {**NEW_MEETING, "agenda": "auto"})

    board.post(url("template_edit", annual.pk), {"name": "Annual", "kind": "annual", "items": "X"})

    assert len(titles(Meeting.objects.get())) == 3


@pytest.mark.parametrize("role", ["Treasurer", "Read-only"])
def test_others_only_look_at_templates(login, templates, role):
    client = login("someone", role)
    annual, _spare = templates

    assert client.get(url("template_list")).status_code == 200
    assert client.get(url("template_create")).status_code == 403
    assert client.get(url("template_edit", annual.pk)).status_code == 403
    assert client.post(url("template_delete", annual.pk)).status_code == 403


def test_the_add_on_page_under_settings_links_to_the_templates(admin, settings):
    settings.REQUIRE_MFA = False
    addons = admin.get(reverse("plugins:list")).content.decode()
    page = admin.get(reverse("plugins:settings", args=["meetings"])).content.decode()

    assert reverse("plugins:settings", args=["meetings"]) in addons
    assert f'href="{url("template_list")}">Agenda templates</a>' in page
