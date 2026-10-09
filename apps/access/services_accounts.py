"""Accounts: invitations, users and groups."""

from django.db import transaction
from django.utils import timezone

from .models import Invitation, User


@transaction.atomic
def apply_invitation(invitation: Invitation, user: User) -> None:
    user.groups.add(*invitation.groups.all())
    if invitation.is_admin:
        user.is_superuser = True
        user.is_staff = True
        user.save(update_fields=["is_superuser", "is_staff"])
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=["accepted_at"])


@transaction.atomic
def accept_invitation(
    invitation: Invitation, *, first_name: str, last_name: str, password: str
) -> User:
    user = User.objects.filter(email__iexact=invitation.email).first()
    if user is None:
        user = User.objects.create_user(
            email=invitation.email, password=password, first_name=first_name, last_name=last_name
        )
    else:
        user.first_name = first_name or user.first_name
        user.last_name = last_name or user.last_name
        user.set_password(password)
        user.is_active = True
        user.save()
    apply_invitation(invitation, user)
    return user


def invite(email: str, *, invited_by, groups=(), is_admin: bool = False, accept_url_builder):
    invitation = Invitation.objects.create(
        email=email.lower(), invited_by=invited_by, is_admin=is_admin
    )
    invitation.groups.set(groups)
    from .tasks import send_invitation_email

    url = accept_url_builder(invitation)
    transaction.on_commit(lambda: send_invitation_email.enqueue(invitation.pk, url))
    return invitation
