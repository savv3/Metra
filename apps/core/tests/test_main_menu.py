import re

import pytest
from django.urls import reverse

from apps.core.templatetags import nav
from apps.plugins import api
from apps.plugins.hooks import NAVIGATION, hooks

pytestmark = pytest.mark.django_db


def menu(client):
    page = client.get(reverse("register:unit_list"), HTTP_ACCEPT_LANGUAGE="en").content.decode()
    start = page.index('<nav class="side-nav"')
    return page[start : page.index("</nav>", start)]


def headings(html):
    return re.findall(r"<h2>([^<]+)</h2>", html)


@pytest.fixture
def nav_item():
    """Register a NavItem for one test, as a plugin would."""
    added = []

    def add(**kwargs):
        item = api.NavItem("Extra", "help:index", **kwargs)
        hooks._items[NAVIGATION].append(item)
        added.append(item)
        return item

    yield add
    for item in added:
        hooks._items[NAVIGATION].remove(item)


def test_links_are_grouped_in_sections(role_client):
    html = menu(role_client("Admin"))

    assert headings(html)[:3] == ["Register", "Finance", "Communication"]
    assert re.search(r'href="/units/" aria-current="page">.*?</svg>[^<]+</a>', html)
    assert html.index(reverse("invoicing:invoice_list")) > html.index("<h2>Finance</h2>")
    assert html.index(reverse("messaging:batch_list")) > html.index("<h2>Communication</h2>")


def test_settings_and_help_are_at_the_bottom(role_client):
    html = menu(role_client("Admin"))
    end = html.index('class="side-nav__end"')

    assert html.index(f'href="{reverse("core:settings")}"') > end
    assert html.index('class="help-link"') > end


def test_a_section_with_nothing_the_user_may_open_is_left_out(make_user, client):
    client.force_login(make_user("reader", "Read-only"))

    html = menu(client)

    for heading in headings(html):
        section = html.split(f"<h2>{heading}</h2>", 1)[1].split("</ul>", 1)[0]
        assert "<a " in section


def test_an_add_on_link_goes_in_its_group(board_client, nav_item):
    nav_item(group="finance", icon="book")

    html = menu(board_client)
    finance = html.split("<h2>Finance</h2>", 1)[1].split("</ul>", 1)[0]

    assert "Extra</a>" in finance
    assert nav.ICONS["book"] in finance


def test_an_add_on_link_without_a_known_group_goes_under_add_ons(board_client, nav_item):
    nav_item(group="nowhere", icon="nope")

    html = menu(board_client)
    addons = html.split("<h2>Add-ons</h2>", 1)[1].split("</ul>", 1)[0]

    assert "Extra</a>" in addons
    assert nav.ICONS[nav.DEFAULT_ICON] in addons


def test_the_api_lists_the_menus_groups_and_icons():
    sections = {key for key, _title in nav.SECTIONS}

    assert set(api.NAV_GROUPS) <= sections
    assert set(api.NAV_ICONS) <= set(nav.ICONS)


def test_signed_out_pages_have_no_menu(client):
    page = client.get(reverse("account_login")).content.decode()

    assert "side-nav" not in page
    assert "menu-button" not in page


def test_phones_get_a_button_that_opens_the_menu(board_client):
    page = board_client.get(reverse("register:unit_list")).content.decode()

    assert 'class="menu-button" href="#main-menu"' in page
    assert 'id="main-menu"' in page
