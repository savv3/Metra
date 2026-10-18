from django.apps import AppConfig


class ExamplePluginConfig(AppConfig):
    name = "metra_example_plugin"
    verbose_name = "Example plugin"
    default_auto_field = "django.db.models.BigAutoField"

    # The plugin stores no personal data. A plugin that does lists it here,
    # for example ["Person: shoe size"], so the export and erasure tools cover it.
    personal_data = []

    def ready(self):
        from apps.plugins import api

        from .providers import LogSMS

        api.add_navigation(
            api.NavItem("Example", "metra_example_plugin:index", "register.view_unit")
        )
        api.add_unit_panel(
            api.Panel(
                "metra_example_plugin/unit_panel.html",
                title="Example panel",
                permission="register.view_unit",
                context=lambda request, unit: {"contacts": unit.unit_contacts.count()},
            )
        )
        api.add_messaging_provider(LogSMS)
        api.add_settings_link(
            api.SettingsLink(
                "Example plugin",
                "metra_example_plugin:index",
                "register.view_unit",
                "What the example plugin adds.",
            )
        )
        api.events.invoice_issued.connect(log_issued_invoice, dispatch_uid="example-plugin")


# Invoice numbers the example plugin has seen being issued, for the tests.
issued = []


def log_issued_invoice(sender, invoice, **kwargs):
    issued.append(invoice.number)
