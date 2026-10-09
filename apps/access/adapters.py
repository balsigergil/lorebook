from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings

from apps.core.portals import INTERNAL, PUBLIC, portal_home

from .models import Invitation


def pending_invitation(email: str) -> Invitation | None:
    if not email:
        return None
    for invitation in Invitation.objects.filter(email__iexact=email, accepted_at__isnull=True):
        if invitation.is_pending:
            return invitation
    return None


class AccountAdapter(DefaultAccountAdapter):
    """Local accounts are created through invitations only."""

    def is_open_for_signup(self, request):
        return False

    def get_login_redirect_url(self, request):
        return portal_home(INTERNAL, request)

    def get_logout_redirect_url(self, request):
        return portal_home(PUBLIC, request)


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """OIDC sign-in. New accounts need an invitation unless OIDC_ALLOW_SIGNUP is set."""

    def is_open_for_signup(self, request, sociallogin):
        if settings.LOREBOOK_OIDC_ALLOW_SIGNUP:
            return True
        return pending_invitation(sociallogin.user.email) is not None

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        invitation = pending_invitation(user.email)
        if invitation is not None:
            from .services_accounts import apply_invitation

            apply_invitation(invitation, user)
        return user
