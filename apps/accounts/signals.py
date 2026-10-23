from allauth.account.models import EmailAddress
from allauth.account.signals import password_reset
from django.dispatch import receiver


@receiver(password_reset)
def verify_email_on_password_reset(sender, request, user, **kwargs):
    """Choosing a password through a reset or setup link proves the person got
    the link, so their address counts as verified. allauth adds the address
    unverified when it makes the link, and then refuses to turn on two-factor
    login, which staff must have, so an install without email (or an admin
    made by create_organisation) could never get past the first login."""
    if not user.email:
        return
    address, _ = EmailAddress.objects.get_or_create(user=user, email=user.email)
    address.verified = True
    if not EmailAddress.objects.filter(user=user, primary=True).exclude(pk=address.pk).exists():
        address.primary = True
    address.save()
