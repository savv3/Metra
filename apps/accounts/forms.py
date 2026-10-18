from allauth.core import context
from allauth.mfa.totp.forms import ActivateTOTPForm as BaseActivateTOTPForm
from allauth.mfa.totp.internal.auth import SECRET_SESSION_KEY


class ActivateTOTPForm(BaseActivateTOTPForm):
    """allauth's form, but the secret stays the same while the setup page is
    reloaded. allauth makes a new secret on every page load, so any second
    load (a reload, another tab, the browser fetching an icon that is
    redirected to this page) silently replaced the secret the user had just
    scanned, and every code was then "incorrect"."""

    def __init__(self, *args, **kwargs):
        kept = context.request.session.get(SECRET_SESSION_KEY)
        super().__init__(*args, **kwargs)
        if kept and not self.is_bound:
            context.request.session[SECRET_SESSION_KEY] = self.secret = kept
