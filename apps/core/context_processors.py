from django.conf import settings


def languages(request):
    """Which languages are machine translated, for the notice in the page, and
    the release version, shown to signed-in users in the account menu, and
    whether this is a demo site, for its banner and login hint."""
    return {
        "DEMO": settings.DEMO,
        "DEMO_RESET_TIME": settings.DEMO_RESET_TIME,
        "DEMO_USERNAME": settings.DEMO_USERNAME,
        "DEMO_PASSWORD": settings.DEMO_PASSWORD,
        "MACHINE_TRANSLATED_LANGUAGES": settings.MACHINE_TRANSLATED_LANGUAGES,
        "METRA_VERSION": settings.METRA_VERSION,
    }
