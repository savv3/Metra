from allauth.mfa.models import Authenticator
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .roles import role_label
from .twofactor import requires_two_factor


@login_required
def profile(request):
    """The signed-in user's own account: who they are, and their login security.

    Every user may see their own account, so this checks login rather than a
    model permission.
    """
    authenticators = {a.type: a for a in Authenticator.objects.filter(user=request.user)}
    recovery = authenticators.get(Authenticator.Type.RECOVERY_CODES)
    context = {
        "roles": sorted(role_label(group) for group in request.user.groups.all()),
        "totp": authenticators.get(Authenticator.Type.TOTP),
        "recovery_unused": len(recovery.wrap().get_unused_codes()) if recovery else None,
        "two_factor_required": requires_two_factor(request.user),
    }
    return render(request, "accounts/profile.html", context)
