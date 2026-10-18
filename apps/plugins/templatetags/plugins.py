import logging

from django import template
from django.conf import settings
from django.template.loader import render_to_string
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html_join
from django.utils.safestring import mark_safe

from ..hooks import NAVIGATION, PERSON_PANELS, SETTINGS_LINKS, UNIT_PANELS, hooks

register = template.Library()
logger = logging.getLogger(__name__)

PANELS = {"unit": UNIT_PANELS, "person": PERSON_PANELS}


def _allowed(user, permission):
    return not permission or user.has_perm(permission)


@register.simple_tag(takes_context=True)
def plugin_navigation(context):
    """Menu links added by plugins."""
    user = context["request"].user
    links = []
    for item in hooks.get(NAVIGATION):
        if not _allowed(user, item.permission):
            continue
        try:
            links.append((reverse(item.url_name), item.label))
        except NoReverseMatch:
            logger.exception("Plugin menu item %r has no URL", item.label)
    return format_html_join("\n", '<a href="{}">{}</a>', links)


@register.simple_tag(takes_context=True)
def plugin_panels(context, kind, obj):
    """Sections plugins add to unit ("unit") or person ("person") pages.

    A plugin that fails while rendering is left out (and logged) rather than
    breaking the page, except in development, where the error shows.
    """
    request = context["request"]
    html = []
    for panel in hooks.get(PANELS[kind]):
        if not _allowed(request.user, panel.permission):
            continue
        try:
            extra = panel.context(request, obj) if panel.context else {}
            html.append(
                render_to_string(
                    panel.template,
                    {"object": obj, "title": panel.title, "perms": context.get("perms"), **extra},
                    request=request,
                )
            )
        except Exception:
            if settings.DEBUG:
                raise
            logger.exception("Plugin panel %s failed", panel.template)
    return mark_safe("\n".join(html))


@register.simple_tag(takes_context=True)
def plugin_settings_links(context):
    """(url, label, description) for the plugins' links on the Settings page."""
    user = context["request"].user
    links = []
    for link in hooks.get(SETTINGS_LINKS):
        if not _allowed(user, link.permission):
            continue
        try:
            links.append((reverse(link.url_name), link.label, link.description))
        except NoReverseMatch:
            logger.exception("Plugin settings link %r has no URL", link.label)
    return links
