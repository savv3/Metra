from django.conf import settings


def languages(request):
    """Which languages are machine translated, for the notice in the page."""
    return {"MACHINE_TRANSLATED_LANGUAGES": settings.MACHINE_TRANSLATED_LANGUAGES}
