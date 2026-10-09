from django.contrib.auth import login
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from apps.core.portals import INTERNAL, portal_home
from apps.core.views import form_invalid, htmx_redirect

from .forms import AcceptInvitationForm
from .models import Invitation
from .services_accounts import accept_invitation


@require_http_methods(["GET", "POST"])
def accept(request, token):
    invitation = get_object_or_404(Invitation, token=token)
    if not invitation.is_pending:
        raise Http404(_("This invitation is no longer valid."))
    form = AcceptInvitationForm(request.POST or None, email=invitation.email)
    if request.method == "POST":
        if not form.is_valid():
            return form_invalid(
                request, form, template="access/accept.html", context={"invitation": invitation}
            )
        user = accept_invitation(
            invitation,
            first_name=form.cleaned_data["first_name"],
            last_name=form.cleaned_data["last_name"],
            password=form.cleaned_data["password1"],
        )
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return htmx_redirect(request, portal_home(INTERNAL, request))
    return render(request, "access/accept.html", {"form": form, "invitation": invitation})
