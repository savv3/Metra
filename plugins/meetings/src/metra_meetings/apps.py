from pathlib import Path

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class MeetingsConfig(AppConfig):
    name = "metra_meetings"
    verbose_name = _("Meetings")
    default_auto_field = "django.db.models.BigAutoField"

    # Attendance links a person (and the unit they represent) to a meeting,
    # with their votes. Approved minutes keep the names as they were: they
    # are the association's records.
    personal_data = [
        "Person: attendance at meetings (name, unit represented, votes, proxy)",
    ]
    # The plugin API versions (apps.plugins.api.API_VERSION) this plugin works with.
    metra_api = [1]

    def ready(self):
        from apps.plugins import api

        from . import member

        api.add_navigation(
            api.NavItem(_("Meetings"), "metra_meetings:meeting_list", "metra_meetings.view_meeting")
        )
        api.add_member_panel(
            api.MemberPanel(
                "metra_meetings/member_panel.html", _("Meeting minutes"), member.panel_context
            )
        )
        # Help articles come with the help pages (Metra 0.3); older releases skip them.
        if hasattr(api, "add_help_articles"):
            api.add_help_articles(
                api.HelpArticles(
                    str(Path(__file__).parent / "help"),
                    order=["meetings"],
                    pages={"metra_meetings": "meetings"},
                )
            )
