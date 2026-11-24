from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group
from django.utils.translation import gettext_lazy as _

from apps.messaging.registry import ProviderError

from . import invites
from .forms import InviteUserForm
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
    """Adding a user invites them by email instead of asking for a password."""

    list_display = ["username", "email", "first_name", "last_name", "is_staff", "invitation"]
    list_filter = ["is_staff", "is_superuser", "is_active", RoleFilter]
    add_form = InviteUserForm
    add_form_template = "admin/accounts/invite_user_form.html"
    add_fieldsets = [(None, {"fields": ["first_name", "last_name", "email", "role"]})]
    actions = ["send_invitation"]

    @admin.display(description=_("waiting for invitation"), boolean=True)
    def invitation(self, user):
        return invites.is_pending(user)

    def response_add(self, request, obj, post_url_continue=None):
        self._invite(request, obj)
        return super().response_add(request, obj, post_url_continue)

    @admin.action(
        description=_("Send a new invitation link to the selected users"),
        permissions=["change"],
    )
    def send_invitation(self, request, queryset):
        for user in queryset:
            if invites.is_pending(user):
                self._invite(request, user)
            else:
                messages.warning(
                    request,
                    _("%(user)s has already chosen a password, so no invitation was sent.")
                    % {"user": user.get_username()},
                )

    def _invite(self, request, user):
        """Email a new link, or show it once when the email cannot go."""
        link = invites.make_link(user, request)
        inviter = request.user.get_full_name() or request.user.get_username()
        values = {"email": user.email, "link": link}
        try:
            sent = invites.send(user, link, inviter=inviter)
        except ProviderError as error:
            values["error"] = error
            messages.warning(
                request,
                _(
                    "The invitation to %(email)s could not be sent (%(error)s). Send them this "
                    "link yourself; it works for a few days and only once: %(link)s"
                )
                % values,
            )
            return
        if sent:
            messages.success(request, _("Invitation sent to %(email)s.") % values)
        else:
            messages.warning(
                request,
                _(
                    "Email is not set up, so no invitation was sent. Send %(email)s this link "
                    "yourself; it works for a few days and only once: %(link)s"
                )
                % values,
            )

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        field = super().formfield_for_manytomany(db_field, request, **kwargs)
        if db_field.name == "groups":
            field.label_from_instance = role_label
        return field


admin.site.unregister(Group)
admin.site.register(Group, RoleGroupAdmin)
admin.site.unregister(User)
admin.site.register(User, RoleUserAdmin)
