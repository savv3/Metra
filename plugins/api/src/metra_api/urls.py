from django.urls import include, path
from drf_spectacular.renderers import OpenApiJsonRenderer
from drf_spectacular.views import SpectacularAPIView
from rest_framework import permissions, routers
from rest_framework.authentication import SessionAuthentication

from . import api_views, views
from .auth import BearerTokenAuthentication, ClientRateThrottle
from .models import ApiClient

app_name = "metra_api"

# Where the plugin is mounted (/plugins/api/) plus the version.
API_PREFIX = "/plugins/api/v1/"

router = routers.SimpleRouter()
router.register("units", api_views.UnitViewSet, basename="unit")
router.register("people", api_views.PersonViewSet, basename="person")
router.register("unit-contacts", api_views.UnitContactViewSet, basename="unitcontact")
router.register("unit-types", api_views.UnitTypeViewSet, basename="unittype")
router.register("person-fields", api_views.PersonFieldViewSet, basename="personfield")
router.register("reading-rounds", api_views.ReadingRoundViewSet, basename="readinground")
router.register("readings", api_views.ReadingViewSet, basename="reading")
router.register("invoices", api_views.InvoiceViewSet, basename="invoice")
router.register("payments", api_views.PaymentViewSet, basename="payment")


class SchemaPermission(permissions.BasePermission):
    """Any API client, or a staff user who may see the API clients."""

    def has_permission(self, request, view):
        if isinstance(request.auth, ApiClient):
            return True
        return request.user.is_authenticated and request.user.has_perm("metra_api.view_apiclient")


class SchemaView(SpectacularAPIView):
    schema = None  # the schema leaves itself out


schema_view = SchemaView.as_view(
    authentication_classes=[BearerTokenAuthentication, SessionAuthentication],
    permission_classes=[SchemaPermission],
    throttle_classes=[ClientRateThrottle],
    renderer_classes=[OpenApiJsonRenderer],
    custom_settings={
        "TITLE": "Metra API",
        "VERSION": "1",
        "SCHEMA_PATH_PREFIX": API_PREFIX.rstrip("/"),
    },
)

urlpatterns = [
    path("", views.client_list, name="client_list"),
    path("clients/new/", views.client_create, name="client_create"),
    path("clients/<int:pk>/rotate/", views.client_rotate, name="client_rotate"),
    path("clients/<int:pk>/revoke/", views.client_revoke, name="client_revoke"),
    path("v1/schema/", schema_view, name="schema"),
    path("v1/docs/", views.docs, name="docs"),
    path("v1/", include(router.urls)),
]
