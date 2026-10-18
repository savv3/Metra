"""The API's endpoints, under /plugins/api/v1/."""

import contextlib

from auditlog.context import set_actor
from auditlog.middleware import AuditlogMiddleware
from django.db.models import Q
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.openapi import AutoSchema
from drf_spectacular.utils import OpenApiParameter
from rest_framework import mixins, pagination, status, viewsets
from rest_framework.parsers import JSONParser
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from apps.plugins import api

from . import serializers
from .auth import (
    ArchivePermissions,
    BearerTokenAuthentication,
    ClientRateThrottle,
    ModelPermissions,
)


class Pagination(pagination.PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


class BearerScheme(OpenApiAuthenticationExtension):
    """Tells the OpenAPI schema how clients authenticate."""

    target_class = "metra_api.auth.BearerTokenAuthentication"
    name = "bearerAuth"

    def get_security_definition(self, auto_schema):
        return {"type": "http", "scheme": "bearer"}


class Schema(AutoSchema):
    """The OpenAPI description: a view's ``filters`` document its list's query
    parameters. (Set per view, so the plugin needs no REST_FRAMEWORK setting.)"""

    def get_override_parameters(self):
        if self.method == "GET" and self._is_list_view():
            return list(getattr(self.view, "filters", []))
        return []

    def get_description(self):
        if self.method == "DELETE" and isinstance(self.view, ArchiveViewSet):
            return "Archives the record. Units and people are never deleted."
        return super().get_description()


class ApiViewMixin:
    """Token authentication, the role's permissions, rate limits, JSON only,
    and audit entries attributed to the client's user."""

    authentication_classes = [BearerTokenAuthentication]
    permission_classes = [ModelPermissions]
    throttle_classes = [ClientRateThrottle]
    pagination_class = Pagination
    renderer_classes = [JSONRenderer]
    parser_classes = [JSONParser]
    schema = Schema()

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        # The audit log middleware ran before the token was checked, when the
        # request had no user; record changes and views as the client's user.
        self._audit = contextlib.ExitStack()
        self._audit.enter_context(
            set_actor(
                request.user,
                remote_addr=AuditlogMiddleware._get_remote_addr(request),
                remote_port=AuditlogMiddleware._get_remote_port(request),
            )
        )

    def finalize_response(self, request, response, *args, **kwargs):
        if audit := getattr(self, "_audit", None):
            audit.close()
        return super().finalize_response(request, response, *args, **kwargs)


def _flag(value):
    return str(value).lower() in {"1", "true", "yes"}


ARCHIVED = OpenApiParameter("archived", bool, description="true for archived records only")
SEARCH = OpenApiParameter("search", str, description="Text to look for")
TAG = OpenApiParameter("tag", str, description="Tag name or id")


class ArchiveViewSet(
    ApiViewMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Records that are archived, never deleted: DELETE archives."""

    permission_classes = [ArchivePermissions]

    def filter_list(self, queryset, params):
        return queryset

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action != "list":
            return queryset
        params = self.request.query_params
        if _flag(params.get("archived", "false")):
            queryset = queryset.filter(archived_at__isnull=False)
        else:
            queryset = queryset.filter(archived_at__isnull=True)
        if tag := params.get("tag", "").strip():
            match = Q(tags__name=tag) | (Q(tags__pk=tag) if tag.isdigit() else Q())
            queryset = queryset.filter(match)
        return self.filter_list(queryset, params).distinct()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        # Opening a record is logged, as on its web page.
        api.log_view(instance)
        return Response(self.get_serializer(instance).data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if not instance.is_archived:
            instance.archive()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UnitViewSet(ArchiveViewSet):
    filters = [
        OpenApiParameter("unit_type", int),
        OpenApiParameter("status", str, enum=["active", "inactive"]),
        TAG,
        ARCHIVED,
        SEARCH,
    ]
    queryset = api.Unit.objects.select_related("unit_type").prefetch_related(
        "tags", "unit_contacts"
    )
    serializer_class = serializers.UnitSerializer

    def filter_list(self, queryset, params):
        if (unit_type := params.get("unit_type", "")).isdigit():
            queryset = queryset.filter(unit_type_id=unit_type)
        if (state := params.get("status", "")) in api.Unit.Status.values:
            queryset = queryset.filter(status=state)
        if q := params.get("search", "").strip():
            queryset = queryset.filter(
                Q(name__icontains=q)
                | Q(street_address__icontains=q)
                | Q(city__icontains=q)
                | Q(contacts__first_name__icontains=q)
                | Q(contacts__last_name__icontains=q)
                | Q(contacts__email__icontains=q)
                | Q(contacts__phone__icontains=q)
            )
        return queryset


class PersonViewSet(ArchiveViewSet):
    filters = [TAG, ARCHIVED, SEARCH]
    queryset = api.Person.objects.prefetch_related("tags", "unit_contacts")
    serializer_class = serializers.PersonSerializer

    def filter_list(self, queryset, params):
        if q := params.get("search", "").strip():
            queryset = queryset.filter(
                Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(email__icontains=q)
                | Q(phone__icontains=q)
                | Q(street_address__icontains=q)
                | Q(city__icontains=q)
            )
        return queryset


class UnitContactViewSet(
    ApiViewMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    filters = [OpenApiParameter("unit", int), OpenApiParameter("person", int)]
    queryset = api.UnitContact.objects.all()
    serializer_class = serializers.ContactSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        for name in ["unit", "person"]:
            if (value := params.get(name, "")).isdigit():
                queryset = queryset.filter(**{f"{name}_id": value})
        return queryset


class UnitTypeViewSet(ApiViewMixin, viewsets.ReadOnlyModelViewSet):
    queryset = api.UnitType.objects.prefetch_related("custom_fields")
    serializer_class = serializers.UnitTypeSerializer


class PersonFieldViewSet(ApiViewMixin, viewsets.ReadOnlyModelViewSet):
    """The custom fields every person has."""

    queryset = api.CustomField.objects.filter(target="person")
    serializer_class = serializers.CustomFieldSerializer
    lookup_field = "key"


class ReadingRoundViewSet(ApiViewMixin, viewsets.ReadOnlyModelViewSet):
    filters = [
        OpenApiParameter("reading_type", int),
        OpenApiParameter("status", str, enum=["draft", "open", "closed"]),
    ]
    queryset = api.ReadingRound.objects.select_related("reading_type")
    serializer_class = serializers.ReadingRoundSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if (reading_type := params.get("reading_type", "")).isdigit():
            queryset = queryset.filter(reading_type_id=reading_type)
        if (state := params.get("status", "")) in api.ReadingRound.Status.values:
            queryset = queryset.filter(status=state)
        return queryset


class ReadingViewSet(
    ApiViewMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    filters = [OpenApiParameter("round", int), OpenApiParameter("unit", int)]
    queryset = api.Reading.objects.select_related("submitted_by", "round__reading_type", "unit")
    serializer_class = serializers.ReadingSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        for name in ["round", "unit"]:
            if (value := params.get(name, "")).isdigit():
                queryset = queryset.filter(**{f"{name}_id": value})
        return queryset


class InvoiceViewSet(ApiViewMixin, viewsets.ReadOnlyModelViewSet):
    """Invoices and credit notes. Read only: issued invoices never change."""

    filters = [
        OpenApiParameter("status", str, enum=["draft", "issued", "paid", "credited"]),
        OpenApiParameter("kind", str, enum=["invoice", "credit_note"]),
        OpenApiParameter("unit", int),
        OpenApiParameter("person", int),
    ]

    queryset = api.Invoice.objects.prefetch_related("lines")
    serializer_class = serializers.InvoiceSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if (state := params.get("status", "")) in api.Invoice.Status.values:
            queryset = queryset.filter(status=state)
        if (kind := params.get("kind", "")) in api.Invoice.Kind.values:
            queryset = queryset.filter(kind=kind)
        for name in ["unit", "person"]:
            if (value := params.get(name, "")).isdigit():
                queryset = queryset.filter(**{f"{name}_id": value})
        return queryset


class PaymentViewSet(ApiViewMixin, viewsets.ReadOnlyModelViewSet):
    """Payments recorded on invoices. Read only."""

    filters = [OpenApiParameter("invoice", int)]

    queryset = api.Payment.objects.all()
    serializer_class = serializers.PaymentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if (invoice := self.request.query_params.get("invoice", "")).isdigit():
            queryset = queryset.filter(invoice_id=invoice)
        return queryset
