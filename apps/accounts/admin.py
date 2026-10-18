from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group
from django.utils.translation import gettext_lazy as _

from .roles import role_label

User = get_user_model()


class RoleFilter(admin.SimpleListFilter):
    title = _("role")
    parameter_name = "role"

    def lookups(self, request, model_admin):
        return [(group.pk, role_label(group)) for group in Group.objects.order_by("name")]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(groups__pk=self.value())
        return queryset


class RoleGroupAdmin(GroupAdmin):
    list_display = ["role_name"]

    @admin.display(description=_("name"), ordering="name")
    def role_name(self, group):
        return role_label(group)


class RoleUserAdmin(UserAdmin):
    list_filter = ["is_staff", "is_superuser", "is_active", RoleFilter]

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        field = super().formfield_for_manytomany(db_field, request, **kwargs)
        if db_field.name == "groups":
            field.label_from_instance = role_label
        return field


admin.site.unregister(Group)
admin.site.register(Group, RoleGroupAdmin)
admin.site.unregister(User)
admin.site.register(User, RoleUserAdmin)
