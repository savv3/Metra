"""The built-in roles and their names as people see them.

The groups keep their English names in the database (Admin, Board,
Treasurer, Read-only): the data migration and permission code use them as
keys. Wherever a group is shown, ``role_label`` translates the built-in
ones; groups an admin creates later keep the name they were given.
"""

from django.utils.translation import pgettext_lazy

ROLE_LABELS = {
    "Admin": pgettext_lazy("role", "Admin"),
    "Board": pgettext_lazy("role", "Board"),
    "Treasurer": pgettext_lazy("role", "Treasurer"),
    "Read-only": pgettext_lazy("role", "Read-only"),
}


def role_label(group):
    """The name to show for a group (or a group name) in the current language."""
    name = getattr(group, "name", group)
    return str(ROLE_LABELS.get(name, name))
