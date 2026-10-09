from django.core.mail import send_mail
from django.tasks import task
from django.template.loader import render_to_string

from apps.core.models import SiteSettings

from .models import Invitation


@task
def send_invitation_email(invitation_id: int, accept_url: str) -> None:
    invitation = Invitation.objects.select_related("invited_by").filter(pk=invitation_id).first()
    if invitation is None or not invitation.is_pending:
        return
    context = {"invitation": invitation, "accept_url": accept_url, "site": SiteSettings.load()}
    send_mail(
        subject=render_to_string("access/email/invitation_subject.txt", context).strip(),
        message=render_to_string("access/email/invitation.txt", context),
        from_email=None,
        recipient_list=[invitation.email],
    )
