from django import template
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

register = template.Library()

# The sections of the main menu, in order. Add-ons pick one with NavItem.group;
# links with no known group go under "Add-ons".
SECTIONS = (
    ("register", _("Register")),
    ("finance", _("Finance")),
    ("communication", _("Communication")),
    ("addons", _("Add-ons")),
)

# The menu's own links: (section, URL name, label, permission, icon). A label
# of None is the register's own word for units.
CORE_ITEMS = (
    ("register", "register:unit_list", None, "register.view_unit", "home"),
    ("register", "register:person_list", _("People"), "register.view_person", "people"),
    ("register", "readings:round_list", _("Readings"), "readings.view_readinground", "gauge"),
    ("finance", "invoicing:invoice_list", _("Invoices"), "invoicing.view_invoice", "invoice"),
    (
        "communication",
        "messaging:batch_list",
        _("Send-outs"),
        "messaging.view_messagebatch",
        "send",
    ),
)

# Line icons (24x24, drawn with the text colour). Add-ons name one with NavItem.icon.
ICONS = {
    "home": '<path d="M3 10.5 12 3l9 7.5V21H3z"/><path d="M9 21v-6h6v6"/>',
    "people": '<circle cx="9" cy="8" r="4"/><path d="M2 21a7 7 0 0 1 14 0"/>'
    '<path d="M16 4a4 4 0 0 1 0 8M22 21a7 7 0 0 0-4-6.3"/>',
    "gauge": '<path d="M12 14l4-4"/><path d="M3.3 19a10 10 0 1 1 17.4 0z"/>',
    "invoice": '<path d="M6 2h9l5 5v15H6z"/><path d="M14 2v6h6M9 13h6M9 17h6"/>',
    "send": '<path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4z"/>',
    "book": '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5z"/>'
    '<path d="M4 19.5V21h16"/>',
    "calendar": '<rect x="3" y="4" width="18" height="18" rx="2"/>'
    '<path d="M16 2v4M8 2v4M3 10h18"/>',
    "chart": '<path d="M3 3v18h18"/><path d="M7 15v2M12 10v7M17 6v11"/>',
    "mail": '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 6-10 7L2 6"/>',
    "server": '<rect x="2" y="3" width="20" height="8" rx="2"/>'
    '<rect x="2" y="13" width="20" height="8" rx="2"/><path d="M6 7h.01M6 17h.01"/>',
    "list": '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    "box": '<path d="M21 8 12 3 3 8v8l9 5 9-5z"/><path d="m3 8 9 5 9-5M12 13v8"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06'
    "a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0"
    "v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06"
    "A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9"
    "a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68"
    "a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33"
    "l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21"
    'a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
    "help": '<circle cx="12" cy="12" r="10"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3"/>'
    '<path d="M12 17h.01"/>',
}
DEFAULT_ICON = "box"


@register.simple_tag
def menu_icon(name):
    """An icon from ICONS, or the default one for an unknown name."""
    paths = ICONS.get(name) or ICONS[DEFAULT_ICON]
    return mark_safe(
        '<svg class="menu-icon" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"'
        ' focusable="false" fill="none" stroke="currentColor" stroke-width="2"'
        f' stroke-linecap="round" stroke-linejoin="round">{paths}</svg>'
    )


def _item(request, url, label, icon):
    return {"url": url, "label": label, "icon": icon, "current": request.path.startswith(url)}


@register.inclusion_tag("_main_menu.html", takes_context=True)
def main_menu(context):
    """The main menu: sections of links the user may open, then Settings and Help."""
    from apps.help.articles import url_for_request
    from apps.plugins.templatetags.plugins import navigation_items

    from ..settings_page import can_open

    request = context["request"]
    user = request.user
    items = {key: [] for key, _title in SECTIONS}
    for section, url_name, label, permission, icon in CORE_ITEMS:
        if user.has_perm(permission):
            if label is None:
                label = context.get("unit_word_plural")
                label = label() if callable(label) else label
            items[section].append(_item(request, reverse(url_name), label, icon))
    for nav_item, url in navigation_items(user):
        section = nav_item.group if nav_item.group in items else "addons"
        items[section].append(_item(request, url, nav_item.label, nav_item.icon))

    settings_item = None
    if can_open(user):
        settings_item = _item(request, reverse("core:settings"), _("Settings"), "settings")
    help_url, help_current = url_for_request(request)
    return {
        "sections": [(title, items[key]) for key, title in SECTIONS if items[key]],
        "settings_item": settings_item,
        "help": {"url": help_url, "current": help_current},
    }
