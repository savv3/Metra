"""A small rate limit for the public member pages, kept in Django's cache.

Every visit counts against the visitor's address; a token that matches no
active link counts again, more strictly, so guessing tokens is slow.
"""

from django.conf import settings
from django.core.cache import cache

VISITS = (60, 10 * 60)  # 60 page loads per 10 minutes
FAILURES = (10, 60 * 60)  # 10 unknown or expired tokens per hour


def client_ip(request):
    if settings.TRUST_X_FORWARDED_FOR:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            # The proxy appends the address it saw; earlier entries can be forged.
            return forwarded.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR", "")


def _key(kind, ip):
    return f"selfservice:{kind}:{ip}"


def _count(kind, ip, window):
    key = _key(kind, ip)
    cache.add(key, 0, window)
    try:
        return cache.incr(key)
    except ValueError:  # expired between add and incr
        cache.set(key, 1, window)
        return 1


def allow_visit(request):
    """Count a visit; False when the visitor is over either limit."""
    ip = client_ip(request)
    if cache.get(_key("fail", ip), 0) >= FAILURES[0]:
        return False
    return _count("visit", ip, VISITS[1]) <= VISITS[0]


def record_failure(request):
    _count("fail", client_ip(request), FAILURES[1])
