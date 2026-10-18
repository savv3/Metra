"""Settings for the test suite: development defaults, no secrets needed."""

import os

os.environ.setdefault("METRA_DEBUG", "true")
os.environ.setdefault("METRA_HUEY_IMMEDIATE", "true")
# Tests run as production does: staff must use two-factor login.
os.environ.setdefault("METRA_REQUIRE_MFA", "true")
# The example plugin (plugins/example, a dev dependency) is loaded the way an
# installation would load it, so the tests cover the real plugin path.
os.environ.setdefault("METRA_PLUGINS", "example,webhooks")

from config.settings import *  # noqa: E402, F403

# Tests check the real templates, not hashed static file names.
STORAGES["staticfiles"]["BACKEND"] = "django.contrib.staticfiles.storage.StaticFilesStorage"  # noqa: F405

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
BASE_URL = "https://register.example.com"

# Never send real messages from tests.
MESSAGING = {**MESSAGING, "sms_provider": "dummy", "email_provider": "django"}  # noqa: F405
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
