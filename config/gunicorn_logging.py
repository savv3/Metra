"""Gunicorn's access log, without the secrets that are part of some addresses.

Member self-service links, SMS file links, newsletter unsubscribe links,
invitation and password links and the 46elks delivery address carry their
token in the path, and the member page's own form posts send it back as
Referer. The database keeps only a hash of member tokens, and anyone holding
an invitation link could choose the new user's password, so the log must not
keep the token itself.
"""

import re

from gunicorn.glogging import Logger

SECRET_PATH = re.compile(
    r"(/m/|/f/|/unsubscribe/|/accounts/password/reset/key/|/plugins/46elks/delivery/)[^/?#\s]+"
)


def redact(value):
    return SECRET_PATH.sub(r"\1[redacted]", value) if isinstance(value, str) else value


class RedactingLogger(Logger):
    def atoms(self, resp, req, environ, request_time):
        atoms = super().atoms(resp, req, environ, request_time)
        for key in ("r", "U", "f", "{referer}i"):
            if key in atoms:
                atoms[key] = redact(atoms[key])
        return atoms
