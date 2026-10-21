"""What members see behind their personal link: the approved minutes."""

from django.http import HttpResponse
from django.views.decorators.cache import never_cache

from apps.plugins import api

from . import documents
from .models import Meeting

SHOWN = 20


def published():
    """Minutes members may read: approved, and meant for them."""
    return Meeting.objects.filter(status=Meeting.Status.APPROVED, members_can_read=True).order_by(
        "-starts_at", "-pk"
    )


def panel_context(request, member_link):
    return {"meetings": published()[:SHOWN]}


@never_cache
def minutes_pdf(request, token, pk):
    """The approved minutes as a PDF, for the member behind the link."""
    link = api.member_link(request, token)
    if link is None:
        return api.member_unavailable(request)
    meeting = published().filter(pk=pk).first()
    if meeting is None:
        return api.member_unavailable(request)
    try:
        pdf = documents.minutes_pdf(meeting)
    except api.PDFUnavailable:
        return api.member_unavailable(request)
    link.log_access(request, meeting)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{documents.minutes_filename(meeting)}"'
    return api.member_response(response)
