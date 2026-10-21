import pytest
from django.urls import reverse

from apps.help import articles
from apps.plugins import api
from apps.plugins.hooks import HELP_ARTICLES, hooks

pytestmark = pytest.mark.django_db

LANGUAGES = ["sv", "en", "fi"]


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_core_article_exists_in_every_language(language):
    for slug in articles.ORDER:
        path = articles.FOLDER / language / f"{slug}.md"
        assert path.is_file(), path
        assert path.read_text(encoding="utf-8").startswith("# "), path


def test_the_help_index_lists_the_articles_in_the_users_language(board_client):
    swedish = board_client.get(reverse("help:index")).content.decode()
    english = board_client.get(reverse("help:index"), HTTP_ACCEPT_LANGUAGE="en").content.decode()

    assert "Kom igång" in swedish and "Fakturering" in swedish
    assert "Getting started" in english and "Invoicing" in english


def test_an_article_is_rendered_from_markdown(board_client):
    page = board_client.get(reverse("help:article", args=["roles"]), HTTP_ACCEPT_LANGUAGE="en")

    html = page.content.decode()
    assert "<h1>Users, roles and two-factor login</h1>" in html
    assert "<table>" in html and "<td>Treasurer</td>" in html
    assert 'aria-current="page">Users, roles and two-factor login</a>' in html


def test_unknown_articles_are_not_found(board_client):
    assert board_client.get(reverse("help:article", args=["nope"])).status_code == 404
    assert articles.get("../../config/settings") is None


def test_finnish_articles_carry_the_machine_translation_notice(board_client):
    board_client.post(reverse("set_language"), {"language": "fi", "next": "/"})

    html = board_client.get(reverse("help:article", args=["readings"])).content.decode()

    assert 'class="message machine-translation"' in html
    assert '<article class="help-body" lang="fi">' in html


def test_search_finds_articles_with_every_word(board_client):
    page = board_client.get(
        reverse("help:index"), {"q": "credit note"}, HTTP_ACCEPT_LANGUAGE="en"
    ).content.decode()
    assert reverse("help:article", args=["invoicing"]) in page

    empty = board_client.get(
        reverse("help:index"), {"q": "zebra unicorn"}, HTTP_ACCEPT_LANGUAGE="en"
    ).content.decode()
    assert "No help article matches" in empty


def test_title_matches_come_first():
    results = articles.search("backups", "en")

    assert results[0].article.slug == "backups"


@pytest.mark.parametrize(
    "url_name, slug",
    [
        ("register:unit_list", "register"),
        ("readings:round_list", "readings"),
        ("messaging:batch_list", "messages"),
        ("invoicing:invoice_list", "invoicing"),
        ("accounts:profile", "roles"),
    ],
)
def test_every_main_page_links_to_its_article(role_client, url_name, slug):
    page = role_client("Admin").get(reverse(url_name)).content.decode()

    assert f'<a href="{reverse("help:article", args=[slug])}" class="help-link"' in page


def test_help_needs_a_login(client):
    response = client.get(reverse("help:index"))

    assert response.status_code == 302


@pytest.fixture
def plugin_articles(tmp_path):
    (tmp_path / "en").mkdir()
    (tmp_path / "en" / "meetings.md").write_text("# Meetings\n\nHow to hold the annual meeting.")
    extra = api.add_help_articles(
        api.HelpArticles(str(tmp_path), order=["meetings"], pages={"core": "meetings"})
    )
    yield extra
    hooks._items[HELP_ARTICLES].remove(extra)


def test_plugins_add_articles_and_page_links(board_client, plugin_articles):
    english = board_client.get(reverse("help:index"), HTTP_ACCEPT_LANGUAGE="en").content.decode()
    assert "Meetings" in english

    # Not written in Swedish: shown in English, saying so.
    swedish = board_client.get(reverse("help:article", args=["meetings"])).content.decode()
    assert "How to hold the annual meeting." in swedish
    assert 'lang="en"' in swedish
    assert articles.for_page("core") == "meetings"
