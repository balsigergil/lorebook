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


def test_thread_reply_resolve(client, editor, admin_user, translation):
    client.force_login(editor)
    url = reverse("comments:panel", args=[translation.pk])
    assert client.get(url).status_code == 200
    response = client.post(url, {"body": ""}, **HX)
    assert response.status_code == 422
    response = client.post(url, {"body": "Une question ?"}, **HX)
    assert "Une question ?" in response.content.decode()
    thread = Thread.objects.get()

    client.force_login(admin_user)
    response = client.post(
        reverse("comments:reply", args=[thread.pk]), {f"reply-{thread.pk}-body": "Réponse"}, **HX
    )
    assert "Réponse" in response.content.decode()
    client.post(reverse("comments:resolve", args=[thread.pk]), {"resolved": "1"}, **HX)
    thread.refresh_from_db()
    assert thread.is_resolved and thread.resolved_by == admin_user


def test_comments_are_for_editors_only(client, reader, outsider, translation):
    url = reverse("comments:panel", args=[translation.pk])
    assert client.get(url).status_code == 403
    # Readers of the collection never see the comments, even on the internal portal.
    for user in (reader, outsider):
        client.force_login(user)
        assert client.get(url).status_code == 404
        assert client.post(url, {"body": "Hello"}).status_code == 404
    assert not Thread.objects.exists()


def test_only_author_or_editor_resolves(client, editor, editors, translation):
    from apps.comments.services import start_thread

    thread = start_thread(translation, editor, "Hello")
    other = type(editor).objects.create_user("other@example.com", "x")
    other.groups.add(editors)
    client.force_login(other)
    response = client.post(reverse("comments:resolve", args=[thread.pk]), {"resolved": "1"})
    # Every editor of the collection can resolve a thread.
    assert response.status_code == 200


def test_author_deletes_own_comment(client, editor, editors, translation):
    from apps.comments.services import reply, start_thread

    thread = start_thread(translation, editor, "Première")
    other = type(editor).objects.create_user("other@example.com", "x")
    other.groups.add(editors)
    answer = reply(thread, other, "Seconde")
    first = thread.comments.get(body="Première")

    client.force_login(editor)
    response = client.get(reverse("comments:panel", args=[translation.pk]))
    body = response.content.decode()
    assert reverse("comments:delete", args=[first.pk]) in body
    assert reverse("comments:delete", args=[answer.pk]) not in body
    # Someone else's comment: refused.
    response = client.post(reverse("comments:delete", args=[answer.pk]), **HX)
    assert response.status_code == 403
    response = client.post(reverse("comments:delete", args=[first.pk]), **HX)
    assert response.status_code == 200
    assert "Première" not in response.content.decode()
    assert list(thread.comments.values_list("body", flat=True)) == ["Seconde"]


def test_admin_deletes_any_comment_and_empty_threads_go(client, editor, admin_user, translation):
    from apps.comments.services import start_thread

    thread = start_thread(translation, editor, "Hello")
    client.force_login(admin_user)
    response = client.post(reverse("comments:delete", args=[thread.comments.get().pk]), **HX)
    assert response.status_code == 200
    assert not Thread.objects.exists()


def test_comments_respect_article_restrictions(client, editor, translation):
    from django.contrib.auth.models import Group

    translation.article.read_groups.add(Group.objects.create(name="Board"))
    client.force_login(editor)
    # Editors keep access: restrictions apply to readers.
    assert client.get(reverse("comments:panel", args=[translation.pk])).status_code == 200
