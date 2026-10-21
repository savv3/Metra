from django import template
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext as _

from .. import articles

register = template.Library()


@register.simple_tag(takes_context=True)
def help_link(context):
    """A "Help" link to the article that fits the current page."""
    request = context.get("request")
    match = getattr(request, "resolver_match", None)
    slug = articles.for_page(match.namespace) if match else None
    if slug and articles.get(slug):
        url = reverse("help:article", args=[slug])
    else:
        url = reverse("help:index")
    current = ' aria-current="page"' if match and match.namespace == "help" else ""
    return format_html('<a href="{}" class="help-link"{}>{}</a>', url, current, _("Help"))
