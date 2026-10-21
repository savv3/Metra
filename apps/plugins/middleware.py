from django.conf import settings
from django.http import Http404

from . import state


class PluginOffMiddleware:
    """Pages under /plugins/<name>/ are not found while that plugin is off."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        parts = request.path_info.split("/", 3)
        if len(parts) > 2 and parts[1] == "plugins" and parts[2] in settings.PLUGIN_APPS:
            if not state.is_enabled(parts[2]):
                raise Http404
        return self.get_response(request)
