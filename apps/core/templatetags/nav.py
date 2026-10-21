from django import template
from django.urls import reverse
from django.utils.html import format_html

register = template.Library()


@register.filter
def can_open_settings(user):
    """Whether the menu shows Settings: the page has at least one entry for the user."""
    from ..settings_page import can_open

    return can_open(user)


@register.simple_tag(takes_context=True)
def nav_link(context, url_name, label):
    """A menu link, marked as the current section when the page is under it."""
    url = reverse(url_name)
    if context["request"].path.startswith(url):
        return format_html('<a href="{}" aria-current="page">{}</a>', url, label)
    return format_html('<a href="{}">{}</a>', url, label)
