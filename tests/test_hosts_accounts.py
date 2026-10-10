import pytest
from django.core import mail
from django.urls import reverse

from apps.access.models import Invitation, User
from apps.core.models import SiteSettings
from apps.core.portals import portal_reverse

HX = {"HTTP_HX_REQUEST": "true"}


@pytest.fixture
def hosts(db, settings):
    settings.ALLOWED_HOSTS = ["*"]
    site = SiteSettings.load()
    site.main_host = "lorebook.example.com"
    site.public_host = "docs.example.com"
    site.internal_host = "kb.example.com"
    site.save()
    return site


def test_dedicated_domains(client, hosts, published):
    response = client.get("/fr/", HTTP_HOST="docs.example.com")
    assert response.status_code == 200
    # The internal portal lives at the root of its own domain.
    response = client.get("/fr/", HTTP_HOST="kb.example.com")
    assert response.status_code == 302 and "/accounts/login/" in response["Location"]
    # Its path prefix does not exist on the public domain.
    assert client.get("/internal/fr/", HTTP_HOST="docs.example.com").status_code == 404
    # Interfaces without a domain keep their prefix on the other domains.
    assert client.get("/edit/", HTTP_HOST="lorebook.example.com").status_code == 302


def test_cross_portal_urls(hosts, rf):
    assert portal_reverse("internal", "portal:home") == "http://kb.example.com/"
    assert portal_reverse("edit", "edit:dashboard") == "/edit/"
    request = rf.get("/", HTTP_HOST="docs.example.com")
    request.portal_host = "public"
    assert portal_reverse("public", "portal:home", request=request) == "/"
    assert portal_reverse("edit", "edit:dashboard", request=request) == (
        "http://lorebook.example.com/edit/"
    )


def test_signup_is_closed(client, db):
    response = client.get("/accounts/signup/")
    assert response.status_code == 200
    assert "closed" in response.content.decode().lower()


def test_login(client, reader):
    response = client.post("/accounts/login/", {"login": "reader@example.com", "password": "pass"})
    assert response.status_code == 302
    assert response["Location"] == "/internal/"


def test_invitation_flow(client, admin_user, readers, django_capture_on_commit_callbacks):
    client.force_login(admin_user)
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            reverse("edit:users"), {"email": "New@Example.com", "groups": [readers.pk]}, **HX
        )
    assert response.status_code == 200
    invitation = Invitation.objects.get()
    assert invitation.email == "new@example.com"
    assert len(mail.outbox) == 1
    accept_url = reverse("access:accept-invitation", args=[invitation.token])
    assert accept_url in mail.outbox[0].body

    client.logout()
    response = client.post(
        accept_url,
        {"first_name": "Nina", "last_name": "New", "password1": "short", "password2": "short"},
        **HX,
    )
    assert response.status_code == 422
    response = client.post(
        accept_url,
        {
            "first_name": "Nina",
            "last_name": "New",
            "password1": "a-Long-pass-phrase-42",
            "password2": "a-Long-pass-phrase-42",
        },
        **HX,
    )
    assert response.status_code == 200
    user = User.objects.get(email="new@example.com")
    assert list(user.groups.all()) == [readers]
    invitation.refresh_from_db()
    assert invitation.accepted_at is not None
    assert client.get(accept_url).status_code == 404


def test_cannot_demote_self(client, admin_user):
    client.force_login(admin_user)
    response = client.post(
        reverse("edit:user", args=[admin_user.pk]),
        {"first_name": "Ada", "last_name": "", "email": admin_user.email, "is_active": "on"},
        **HX,
    )
    assert response.status_code == 422
    admin_user.refresh_from_db()
    assert admin_user.is_superuser
