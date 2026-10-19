from django.conf import settings


def languages(request):
    """Which languages are machine translated, for the notice in the page, and
    the release version, shown to signed-in users in the account menu."""
    return {
        "MACHINE_TRANSLATED_LANGUAGES": settings.MACHINE_TRANSLATED_LANGUAGES,
        "METRA_VERSION": settings.METRA_VERSION,
    }
