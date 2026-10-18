from django import template

from ..roles import role_label
from ..twofactor import has_two_factor, is_staff, requires_two_factor

register = template.Library()


@register.filter
def role_names(user):
    """The user's roles, translated, for showing next to their name."""
    return ", ".join(sorted(role_label(group) for group in user.groups.all()))


@register.filter
def should_set_up_two_factor(user):
    """Users who may skip two-factor login but have not turned it on yet."""
    return user.is_authenticated and not requires_two_factor(user) and not has_two_factor(user)


@register.filter
def two_factor_not_required(user):
    """Staff on an installation where SCR_REQUIRE_MFA is off: they should know."""
    return is_staff(user) and not requires_two_factor(user)
