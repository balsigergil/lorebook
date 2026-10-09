"""Administration of the instance: settings, languages, glossary, groups, users."""

from django.contrib import messages
from django.contrib.auth.models import Group
from django.db.models import Count
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.access import services_accounts as accounts
from apps.access.models import Invitation, User
from apps.core.models import SiteSettings
from apps.core.views import form_invalid, htmx_redirect
from apps.i18n.models import GlossaryTerm, Language
from apps.i18n.services import enabled_languages

from ..forms import (
    GlossaryTermForm,
    GroupForm,
    GroupMemberForm,
    InvitationForm,
    LanguageForm,
    ProfileForm,
    SiteSettingsForm,
    UserForm,
)
from .common import admin_required, editor_required, sidebar_context


def page(request, template, nav, **context):
    return render(request, template, {**sidebar_context(request), "nav": nav, **context})


# Site settings


@require_http_methods(["GET", "POST"])
@admin_required
def site_settings(request):
    form = SiteSettingsForm(request.POST or None, instance=SiteSettings.load())
    if request.method == "POST":
        if not form.is_valid():
            return form_invalid(request, form)
        form.save()
        messages.success(request, _("Settings saved."))
        return htmx_redirect(request, reverse("edit:settings"))
    return page(request, "editor/admin/settings.html", "settings", form=form)


# Languages


@require_http_methods(["GET", "POST"])
@admin_required
def languages(request):
    form = LanguageForm(request.POST or None)
    form.action = reverse("edit:languages")
    if request.method == "POST":
        if not form.is_valid():
            return form_invalid(request, form)
        form.save()
        messages.success(request, _("Language added."))
        return htmx_redirect(request, form.action)
    return page(
        request,
        "editor/admin/languages.html",
        "languages",
        languages=Language.objects.all(),
        form=form,
    )


@require_POST
@admin_required
def language_update(request, pk):
    language = get_object_or_404(Language, pk=pk)
    action = request.POST.get("action")
    if action == "toggle":
        if language.enabled and Language.objects.filter(enabled=True).count() == 1:
            messages.error(request, _("At least one language must stay enabled."))
        else:
            language.enabled = not language.enabled
            language.save(update_fields=["enabled"])
    elif action in ("up", "down"):
        ordered = list(Language.objects.all())
        index = ordered.index(language)
        target = index - 1 if action == "up" else index + 1
        if 0 <= target < len(ordered):
            ordered[index], ordered[target] = ordered[target], ordered[index]
            for position, item in enumerate(ordered):
                item.position = position
            Language.objects.bulk_update(ordered, ["position"])
            # bulk_update skips signals: refresh the cached list explicitly.
            from apps.i18n.services import invalidate_cache

            invalidate_cache()
    return htmx_redirect(request, reverse("edit:languages"))


# Glossary


@require_GET
@editor_required
def glossary(request):
    form = GlossaryTermForm()
    form.action = reverse("edit:glossary-create")
    form.submit_label = _("Add")
    query = request.GET.get("q", "").strip().lower()
    terms = list(GlossaryTerm.objects.all())
    if query:
        terms = [
            term
            for term in terms
            if any(query in value.lower() for value in term.translations.values())
        ]
    languages = enabled_languages()
    rows = [
        (term, [term.translations.get(language.code, "") for language in languages])
        for term in terms
    ]
    return page(
        request,
        "editor/glossary.html",
        "glossary",
        rows=rows,
        languages=languages,
        form=form,
        query=query,
    )


@require_POST
@editor_required
def glossary_create(request):
    form = GlossaryTermForm(request.POST)
    form.action = reverse("edit:glossary-create")
    form.submit_label = _("Add")
    if not form.is_valid():
        return form_invalid(request, form)
    form.save()
    messages.success(request, _("Term added."))
    return htmx_redirect(request, reverse("edit:glossary"))


@require_http_methods(["GET", "POST"])
@editor_required
def glossary_edit(request, pk):
    term = get_object_or_404(GlossaryTerm, pk=pk)
    form = GlossaryTermForm(request.POST or None, instance=term)
    form.cancel_url = reverse("edit:glossary")
    if request.method == "POST":
        if request.POST.get("delete") == "1":
            term.delete()
            messages.success(request, _("Term deleted."))
            return htmx_redirect(request, reverse("edit:glossary"))
        if not form.is_valid():
            return form_invalid(request, form)
        form.save()
        messages.success(request, _("Term saved."))
        return htmx_redirect(request, reverse("edit:glossary"))
    return page(request, "editor/glossary_edit.html", "glossary", form=form, term=term)


# Groups


@require_http_methods(["GET", "POST"])
@admin_required
def groups(request):
    form = GroupForm(request.POST or None)
    form.action = reverse("edit:groups")
    form.submit_label = _("Create the group")
    if request.method == "POST":
        if not form.is_valid():
            return form_invalid(request, form)
        group = form.save()
        messages.success(request, _("Group created."))
        return htmx_redirect(request, reverse("edit:group", args=[group.pk]))
    return page(
        request,
        "editor/admin/groups.html",
        "groups",
        groups=Group.objects.annotate(
            member_count=Count("user", distinct=True),
            collection_count=Count("collection_roles", distinct=True),
        ).order_by("name"),
        form=form,
    )


@require_http_methods(["GET", "POST"])
@admin_required
def group_detail(request, pk):
    group = get_object_or_404(Group, pk=pk)
    rename_form = GroupForm(instance=group, prefix="rename")
    rename_form.action = reverse("edit:group", args=[group.pk])
    member_form = GroupMemberForm(group=group, prefix="member")
    member_form.action = reverse("edit:group", args=[group.pk])
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "rename":
            rename_form = GroupForm(request.POST, instance=group, prefix="rename")
            rename_form.action = reverse("edit:group", args=[group.pk])
            if not rename_form.is_valid():
                return form_invalid(request, rename_form, context={"action_name": "rename"})
            rename_form.save()
        elif action == "add":
            member_form = GroupMemberForm(request.POST, group=group, prefix="member")
            member_form.action = reverse("edit:group", args=[group.pk])
            if not member_form.is_valid():
                return form_invalid(request, member_form, context={"action_name": "add"})
            member_form.cleaned_data["user"].groups.add(group)
        elif action == "remove":
            user = get_object_or_404(User, pk=request.POST.get("user"))
            user.groups.remove(group)
        elif action == "delete":
            group.delete()
            messages.success(request, _("Group deleted."))
            return htmx_redirect(request, reverse("edit:groups"))
        messages.success(request, _("Group updated."))
        return htmx_redirect(request, reverse("edit:group", args=[group.pk]))
    rename_form.submit_label = _("Rename")
    return page(
        request,
        "editor/admin/group.html",
        "groups",
        group=group,
        members=group.user_set.order_by("first_name", "last_name", "email"),
        roles=group.collection_roles.select_related("collection"),
        rename_form=rename_form,
        member_form=member_form,
    )


# Users and invitations


def accept_url_builder(request):
    def build(invitation: Invitation) -> str:
        return request.build_absolute_uri(
            reverse("access:accept-invitation", args=[invitation.token])
        )

    return build


@require_http_methods(["GET", "POST"])
@admin_required
def users(request):
    form = InvitationForm(request.POST or None)
    form.action = reverse("edit:users")
    if request.method == "POST":
        if not form.is_valid():
            return form_invalid(request, form)
        accounts.invite(
            form.cleaned_data["email"],
            invited_by=request.user,
            groups=form.cleaned_data["groups"],
            is_admin=form.cleaned_data["is_admin"],
            accept_url_builder=accept_url_builder(request),
        )
        messages.success(request, _("Invitation sent."))
        return htmx_redirect(request, reverse("edit:users"))
    invitations = [
        invitation
        for invitation in Invitation.objects.filter(accepted_at__isnull=True).select_related(
            "invited_by"
        )
    ]
    return page(
        request,
        "editor/admin/users.html",
        "users",
        users=User.objects.prefetch_related("groups").order_by("-is_active", "first_name", "email"),
        invitations=invitations,
        form=form,
    )


@require_POST
@admin_required
def invitation_action(request, pk):
    invitation = get_object_or_404(Invitation, pk=pk, accepted_at__isnull=True)
    if request.POST.get("action") == "resend":
        from apps.access.tasks import send_invitation_email

        send_invitation_email.enqueue(invitation.pk, accept_url_builder(request)(invitation))
        messages.success(request, _("Invitation sent again."))
    else:
        invitation.delete()
        messages.success(request, _("Invitation cancelled."))
    return htmx_redirect(request, reverse("edit:users"))


@require_http_methods(["GET", "POST"])
@admin_required
def user_detail(request, pk):
    user = get_object_or_404(User, pk=pk)
    form = UserForm(request.POST or None, instance=user)
    form.cancel_url = reverse("edit:users")
    if request.method == "POST":
        if not form.is_valid():
            return form_invalid(request, form)
        if user.pk == request.user.pk and (
            not form.cleaned_data["is_superuser"] or not form.cleaned_data["is_active"]
        ):
            form.add_error(None, _("You cannot remove your own administrator access."))
            return form_invalid(request, form)
        form.save()
        messages.success(request, _("User saved."))
        return htmx_redirect(request, reverse("edit:users"))
    return page(request, "editor/admin/user.html", "users", form=form, managed_user=user)


# Profile


@require_http_methods(["GET", "POST"])
@editor_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST":
        if not form.is_valid():
            return form_invalid(request, form)
        form.save()
        messages.success(request, _("Profile saved."))
        return htmx_redirect(request, reverse("edit:profile"))
    return page(request, "editor/profile.html", "profile", form=form)
