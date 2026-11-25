import datetime

from gunicorn.config import Config

from config.gunicorn_logging import RedactingLogger


class Response:
    status = "200 OK"
    sent = 10
    headers = []


def _atoms(path, referer):
    environ = {
        "REQUEST_METHOD": "GET",
        "RAW_URI": path,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "HTTP_REFERER": referer,
    }
    logger = RedactingLogger(Config())
    return logger.atoms(Response(), [("REFERER", referer)], environ, datetime.timedelta(0))


def test_member_tokens_stay_out_of_the_access_log():
    atoms = _atoms("/m/secret-token/?lang=en", "https://example.com/m/secret-token/")

    for key in ("r", "U", "f", "{referer}i"):
        assert "secret-token" not in atoms[key]
    assert atoms["U"] == "/m/[redacted]/?lang=en"


def test_file_link_tokens_stay_out_of_the_access_log():
    atoms = _atoms("/f/secret-token/3/", "-")

    assert atoms["U"] == "/f/[redacted]/3/"


def test_delivery_report_secret_stays_out_of_the_access_log():
    atoms = _atoms("/plugins/46elks/delivery/abc123/", "-")

    assert "abc123" not in atoms["r"]


def test_other_addresses_are_logged_as_they_are():
    assert _atoms("/units/12/", "-")["U"] == "/units/12/"


def test_invitation_and_password_links_stay_out_of_the_access_log():
    atoms = _atoms("/accounts/password/reset/key/2s-abc123-secretkey/", "-")

    assert "secretkey" not in atoms["r"]
    assert atoms["U"] == "/accounts/password/reset/key/[redacted]/"


def test_unsubscribe_tokens_stay_out_of_the_access_log():
    atoms = _atoms("/unsubscribe/signed-token/", "https://example.com/unsubscribe/signed-token/")

    assert "signed-token" not in atoms["r"] + atoms["{referer}i"]
