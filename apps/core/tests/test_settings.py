import pytest
from django.db import connection


@pytest.mark.django_db
def test_sqlite_enforces_foreign_keys():
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA foreign_keys")
        assert cursor.fetchone()[0] == 1


def _load_settings(**env):
    """Import config.settings in a fresh interpreter with only these SCR_ values."""
    import os
    import subprocess
    import sys

    clean = {k: v for k, v in os.environ.items() if not k.startswith("SCR_")}
    return subprocess.run(
        [sys.executable, "-c", "import config.settings as s; print(s.ALLAUTH_TRUSTED_PROXY_COUNT)"],
        env={**clean, "SCR_DATA_DIR": env.pop("data_dir"), **env},
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("key", ["change-me", "insecure-development-key"])
def test_example_secret_key_is_refused_in_production(tmp_path, key):
    result = _load_settings(data_dir=str(tmp_path), SCR_SECRET_KEY=key)

    assert result.returncode != 0
    assert "example value" in result.stderr


def test_login_rate_limits_trust_the_proxy_only_when_told(tmp_path):
    key = "a-real-secret-key-for-this-test-only"
    behind = _load_settings(
        data_dir=str(tmp_path), SCR_SECRET_KEY=key, SCR_TRUST_X_FORWARDED_FOR="true"
    )
    direct = _load_settings(data_dir=str(tmp_path), SCR_SECRET_KEY=key)

    assert behind.stdout.strip() == "1"
    assert direct.stdout.strip() == "0"


def _require_mfa(tmp_path, **env):
    import os
    import subprocess
    import sys

    clean = {k: v for k, v in os.environ.items() if not k.startswith("SCR_")}
    result = subprocess.run(
        [sys.executable, "-c", "import config.settings as s; print(s.REQUIRE_MFA)"],
        env={**clean, "SCR_DATA_DIR": str(tmp_path), **env},
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_two_factor_is_required_in_production_and_optional_in_development(tmp_path):
    key = "a-real-secret-key-for-this-test-only"

    assert _require_mfa(tmp_path, SCR_SECRET_KEY=key) == "True"
    assert _require_mfa(tmp_path, SCR_DEBUG="true") == "False"
    assert _require_mfa(tmp_path, SCR_DEBUG="true", SCR_REQUIRE_MFA="true") == "True"
    assert _require_mfa(tmp_path, SCR_SECRET_KEY=key, SCR_REQUIRE_MFA="false") == "False"
