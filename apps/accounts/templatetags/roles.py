from django import template

from ..roles import role_label
from ..twofactor import has_two_factor, requires_two_factor

register = template.Library()


@register.filter
def role_names(user):
    """The user's roles, translated, for showing next to their name."""
    return ", ".join(sorted(role_label(group) for group in user.groups.all()))


@register.filter
def should_set_up_two_factor(user):
    """Users who may skip two-factor login but have not turned it on yet."""
    return user.is_authenticated and not requires_two_factor(user) and not has_two_factor(user)
