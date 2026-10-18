import pytest

from metra_webhooks import service
from metra_webhooks.models import WebhookEndpoint

REAL_HTTP_POST = service.http_post


class FakeNetwork:
    """Stands in for the HTTP layer: records requests, answers as told."""

    def __init__(self):
        self.requests = []
        self.answer = (200, "ok")

    def __call__(self, url, body, headers, timeout=10):
        self.requests.append({"url": url, "body": body, "headers": headers})
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


@pytest.fixture(autouse=True)
def network(monkeypatch):
    fake = FakeNetwork()
    monkeypatch.setattr(service, "http_post", fake)
    return fake


@pytest.fixture
def endpoint(db):
    return WebhookEndpoint.objects.create(
        url="https://hooks.example.org/metra", events=["unit.saved", "invoice.issued"]
    )
