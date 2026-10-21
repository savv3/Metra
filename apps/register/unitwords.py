"""What to call units in the interface.

Unit types are configured by an admin. When an installation has exactly one
(unit types cannot be archived, so every type counts), the pages use that
type's own name and plural instead of the general word "unit"."""

from django.utils.translation import gettext as _

from .models import UnitType


def words(request=None):
    """The words for units: ``single_unit_type`` (the only type, or None),
    ``singular`` and ``plural``. Cached on the request when there is one."""
    cached = getattr(request, "_unit_words", None)
    if cached is not None:
        return cached
    types = list(UnitType.objects.all()[:2])
    single = types[0] if len(types) == 1 else None
    result = {
        "single_unit_type": single,
        "singular": single.name if single else _("Unit"),
        "plural": (single.name_plural if single else "") or _("Units"),
    }
    if request is not None:
        request._unit_words = result
    return result
