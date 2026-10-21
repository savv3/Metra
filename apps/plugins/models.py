from auditlog.registry import auditlog
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class PluginState(models.Model):
    """Whether an installed plugin is turned on. A plugin without a row is on."""

    name = models.CharField(_("add-on"), max_length=100, unique=True)
    enabled = models.BooleanField(_("on"), default=True)
    changed_at = models.DateTimeField(_("changed"), default=timezone.now)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("changed by"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = _("add-on")
        verbose_name_plural = _("add-ons")

    def __str__(self):
        return self.name


class PluginSetting(models.Model):
    """A value of a plugin's setting, saved on its settings page. Secrets are
    stored encrypted (see apps.plugins.secrets)."""

    plugin = models.CharField(_("add-on"), max_length=100)
    key = models.CharField(_("setting"), max_length=100)
    value = models.TextField(_("value"), blank=True)
    changed_at = models.DateTimeField(_("changed"), default=timezone.now)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("changed by"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        ordering = ["plugin", "key"]
        verbose_name = _("add-on setting")
        verbose_name_plural = _("add-on settings")
        constraints = [
            models.UniqueConstraint(fields=["plugin", "key"], name="one_value_per_plugin_setting")
        ]

    def __str__(self):
        return f"{self.plugin}: {self.key}"


auditlog.register(PluginState)
# The log says which setting changed, when and by whom, never the value.
auditlog.register(PluginSetting, exclude_fields=["value"])
