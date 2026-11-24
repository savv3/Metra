"""What the invitation commands share: sending the link and saying so."""

from apps.accounts import invites
from apps.messaging.registry import ProviderError


def send(user, link):
    """Email the link; the outcome as fields for the command's JSON."""
    try:
        sent = invites.send(user, link)
    except ProviderError as error:
        return {"sent": False, "error": str(error)}
    if not sent:
        return {"sent": False, "error": "Email is not set up on this install."}
    return {"sent": True}


def report(out, result):
    if result.get("sent"):
        out.write(f"Emailed the link to {result['username']}.")
    elif "sent" in result:
        out.write(f"The link was not emailed: {result['error']}")
    out.write(f"Choose a password here: {result['link']}")
