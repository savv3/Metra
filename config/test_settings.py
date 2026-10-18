"""Settings for the test suite: development defaults, no secrets needed."""

import os

os.environ.setdefault("SCR_DEBUG", "true")
os.environ.setdefault("SCR_HUEY_IMMEDIATE", "true")

from config.settings import *  # noqa: E402, F403

# Tests check the real templates, not hashed static file names.
STORAGES["staticfiles"]["BACKEND"] = "django.contrib.staticfiles.storage.StaticFilesStorage"  # noqa: F405
