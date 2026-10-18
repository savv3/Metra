from apps.register.models import Organisation


class NoIndexMiddleware:
    """Ask search engines not to index any page except the public page at /."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if "X-Robots-Tag" not in response and not self._indexable(request, response):
            response["X-Robots-Tag"] = "noindex, nofollow"
        return response

    @staticmethod
    def _indexable(request, response):
        if request.path != "/" or response.status_code != 200 or request.user.is_authenticated:
            return False
        organisation = Organisation.current()
        return organisation is not None and organisation.public_page
