from django import template

from ..roles import role_label

register = template.Library()


@register.filter
def role_names(user):
    """The user's roles, translated, for showing next to their name."""
    return ", ".join(sorted(role_label(group) for group in user.groups.all()))
