from auditlog.mixins import AuditlogHistoryAdminMixin
from django.contrib import admin
from django.db import models
from django.utils.translation import gettext_lazy as _

from .models import CustomField, Organisation, Person, Tag, Unit, UnitContact, UnitType


class UnitCustomFieldInline(admin.TabularInline):
    model = CustomField
    fields = ["order", "key", "label", "field_type", "choices", "required", "help_text"]
    extra = 0

    def get_queryset(self, request):
        return super().get_queryset(request).filter(target=CustomField.Target.UNIT)


@admin.register(Organisation)
class OrganisationAdmin(AuditlogHistoryAdminMixin, admin.ModelAdmin):
    show_auditlog_history_link = True
    list_display = ["name", "business_id", "country"]
    # A website typed as example.org becomes https://example.org.
    formfield_overrides = {models.URLField: {"assume_scheme": "https"}}
    fieldsets = [
        (
            None,
            {
                "fields": [
                    "name",
                    "business_id",
                    "vat_number",
                    "email",
                    "phone",
                    "street_address",
                    "postal_code",
                    "city",
                    "country",
                ]
            },
        ),
        (
            _("Public page and contact details"),
            {
                "description": _(
                    "Shown to anyone on the public page, on members' pages and in letters, "
                    "together with the email, phone and address above."
                ),
                "fields": [
                    "public_page",
                    "display_name",
                    "description",
                    "website",
                    "emergency_phone",
                    "opening_hours",
                    "logo",
                ],
            },
        ),
    ]

    def has_add_permission(self, request):
        # One installation serves one organisation.
        return not Organisation.objects.exists()


@admin.register(UnitType)
class UnitTypeAdmin(AuditlogHistoryAdminMixin, admin.ModelAdmin):
    show_auditlog_history_link = True
    list_display = ["name", "order"]
    inlines = [UnitCustomFieldInline]

    def save_formset(self, request, form, formset, change):
        for obj in formset.save(commit=False):
            obj.target = CustomField.Target.UNIT
            obj.save()
        for obj in formset.deleted_objects:
            obj.delete()


@admin.register(CustomField)
class CustomFieldAdmin(AuditlogHistoryAdminMixin, admin.ModelAdmin):
    show_auditlog_history_link = True
    list_display = ["label", "key", "target", "unit_type", "field_type", "required", "order"]
    list_filter = ["target", "unit_type"]


@admin.register(Tag)
class TagAdmin(AuditlogHistoryAdminMixin, admin.ModelAdmin):
    show_auditlog_history_link = True
    search_fields = ["name"]


class UnitContactInline(admin.TabularInline):
    model = UnitContact
    autocomplete_fields = ["person"]
    extra = 0


@admin.register(Unit)
class UnitAdmin(AuditlogHistoryAdminMixin, admin.ModelAdmin):
    show_auditlog_history_link = True
    list_display = ["name", "unit_type", "status", "city", "archived_at"]
    list_filter = ["unit_type", "status", "tags"]
    search_fields = ["name", "street_address", "city"]
    inlines = [UnitContactInline]


@admin.register(Person)
class PersonAdmin(AuditlogHistoryAdminMixin, admin.ModelAdmin):
    show_auditlog_history_link = True
    list_display = ["first_name", "last_name", "email", "phone", "archived_at"]
    list_filter = ["tags", "preferred_channel"]
    search_fields = ["first_name", "last_name", "email", "phone"]
