import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from metra_api.models import ApiClient


@pytest.fixture(autouse=True)
def fresh_rate_limits():
    """Rate limit counters live in the cache; start every test with none."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def make_client(db):
    """An ApiClient with the given role, and its token."""

    def make(role="Board", name=None, **extra):
        return ApiClient.create(name=name or f"{role} system", role=role, **extra)

    return make


@pytest.fixture
def api_as(make_client):
    """A DRF test client sending the token of a new ApiClient with ``role``."""

    def login(role="Board", **extra):
        client, token = make_client(role, **extra)
        http = APIClient()
        http.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        http.api_client = client
        return http

    return login
