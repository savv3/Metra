from django.conf import settings
from django.http import HttpResponseRedirect


def switch_language(request):
    """?lang=en sets the language and reloads the page, for public pages whose
    language switch is plain links. None when the request has no ?lang."""
    language = request.GET.get("lang")
    if language not in dict(settings.LANGUAGES):
        return None
    response = HttpResponseRedirect(request.path)
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME,
        language,
        max_age=settings.LANGUAGE_COOKIE_AGE,
        samesite="Lax",
        secure=request.is_secure(),
    )
    return response
