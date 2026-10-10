import pytest
from django.urls import reverse

from apps.comments.models import Thread
from apps.content import services as content

HX = {"HTTP_HX_REQUEST": "true"}


@pytest.fixture
def translation(private_collection, editor):
    translation = content.create_article(private_collection, title="Doc", language="fr")
    content.publish(translation)
    return translation


def test_thread_reply_resolve(client, reader, editor, translation):
    client.force_login(reader)
    url = reverse("comments:panel", args=[translation.pk])
    assert client.get(url).status_code == 200
    response = client.post(url, {"body": ""}, **HX)
    assert response.status_code == 422
    response = client.post(url, {"body": "Une question ?"}, **HX)
    assert "Une question ?" in response.content.decode()
    thread = Thread.objects.get()

    client.force_login(editor)
    response = client.post(
        reverse("comments:reply", args=[thread.pk]), {f"reply-{thread.pk}-body": "Réponse"}, **HX
    )
    assert "Réponse" in response.content.decode()
    client.post(reverse("comments:resolve", args=[thread.pk]), {"resolved": "1"}, **HX)
    thread.refresh_from_db()
    assert thread.is_resolved and thread.resolved_by == editor


def test_only_author_or_editor_resolves(client, reader, outsider, translation, readers):
    from apps.comments.services import start_thread

    thread = start_thread(translation, reader, "Hello")
    other = type(reader).objects.create_user("other@example.com", "x")
    other.groups.add(readers)
    client.force_login(other)
    response = client.post(reverse("comments:resolve", args=[thread.pk]), {"resolved": "1"})
    assert response.status_code == 403


def test_outsiders_and_anonymous_cannot_comment(client, outsider, translation):
    url = reverse("comments:panel", args=[translation.pk])
    assert client.get(url).status_code == 403
    client.force_login(outsider)
    assert client.get(url).status_code == 404


def test_comments_respect_article_restrictions(client, reader, translation):
    from django.contrib.auth.models import Group

    translation.article.read_groups.add(Group.objects.create(name="Board"))
    client.force_login(reader)
    assert client.get(reverse("comments:panel", args=[translation.pk])).status_code == 404
