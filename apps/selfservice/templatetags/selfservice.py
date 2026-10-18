from django import template

from ..models import SelfServiceLink

register = template.Library()


@register.inclusion_tag("selfservice/_unit_links.html", takes_context=True)
def unit_self_service(context, unit):
    """The unit's working self-service links and a button to print a letter."""
    user = context["request"].user
    if not user.has_perm("selfservice.view_selfservicelink"):
        return {"show": False}
    links = SelfServiceLink.objects.active().filter(unit=unit).select_related("person", "round")
    return {
        "show": True,
        "unit": unit,
        "links": links,
        "perms": context.get("perms"),
        "csrf_token": context.get("csrf_token"),
    }
