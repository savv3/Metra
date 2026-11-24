import pytest
from django.template import Context, Template
from django.urls import reverse


@pytest.fixture
def admin(role_client):
    return role_client("Admin")


def test_crumbs_list_the_parent_pages():
    html = Template('{% load nav %}{% crumbs "/a/" "Invoices" "/b/" "Runs" %}').render(Context())

    assert '<nav class="crumbs"' in html
    assert '<li><a href="/a/">Invoices</a></li><li><a href="/b/">Runs</a></li>' in html


def test_unit_page_layout(admin, unit):
    page = admin.get(unit.get_absolute_url(), HTTP_ACCEPT_LANGUAGE="en").content.decode()

    # Archive sits in the More menu, adding a contact opens from a button, and
    # empty fields are left out instead of shown as a dash.
    more = page.split('class="more-menu"')[1].split("</details>")[0]
    assert "Archive</button>" in more
    assert '<details class="add-panel">' in page
    assert "<dt>End date</dt>" not in page
    crumbs = page.split('class="crumbs"')[1].split("</nav>")[0]
    assert f'href="{reverse("register:unit_list")}"' in crumbs


def test_settings_subpages_have_crumbs_not_back_buttons(admin):
    for name in ("messaging:email_settings", "plugins:list"):
        page = admin.get(reverse(name), HTTP_ACCEPT_LANGUAGE="en").content.decode()
        head = page.split('<div class="page-head">')[1].split("</div>")[0]
        assert 'class="crumbs"' in page
        assert reverse("core:settings") not in head
