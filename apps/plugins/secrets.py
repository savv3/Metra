"""Encrypting the secrets in plugin settings, such as API keys.

The key comes from METRA_SETTINGS_KEY, or is derived from METRA_SECRET_KEY
when that is not set. A snapshot restored on another server needs the same
key, or saved secrets cannot be read and must be entered again.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


class SecretUnreadable(Exception):
    """A secret was saved with another key."""


def _fernet():
    material = settings.SETTINGS_KEY or settings.SECRET_KEY
    digest = hashlib.sha256(b"metra-plugin-settings:" + material.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(text):
    return _fernet().encrypt(text.encode()).decode()


def decrypt(token):
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as error:
        raise SecretUnreadable from error
