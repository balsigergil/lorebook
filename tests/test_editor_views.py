import json

import pytest
from django.urls import reverse

from apps.content import services as content
from apps.content.models import Article, ArticleTranslation, Collection

from .conftest import doc

HX = {"HTTP_HX_REQUEST": "true"}


@pytest.fixture
def translation(private_collection, editor):
    return content.create_article(
        private_collection, title="Guide", language="fr", content=doc("Brouillon"), user=editor
    )


def test_editor_requires_editor_role(client, reader, outsider):
    client.force_login(reader)
    assert client.get(reverse("edit:dashboard")).status_code == 403
    client.logout()
    assert client.get(reverse("edit:dashboard")).status_code == 302


def test_dashboard_and_collection(client, editor, translation):
    client.force_login(editor)
    assert client.get(reverse("edit:dashboard")).status_code == 200
    response = client.get(reverse("edit:collection", args=["handbook"]))
    assert response.status_code == 200
    assert "Guide" in response.content.decode()


def test_editor_cannot_manage_permissions(client, editor, private_collection):
    client.force_login(editor)
    url = reverse("edit:collection-permissions", args=["handbook"])
    assert client.get(url).status_code == 403


def test_create_article_htmx(client, editor, private_collection):
    client.force_login(editor)
    url = reverse("edit:article-create", args=["handbook"])
    response = client.post(url, {"title": "", "language": "fr"}, **HX)
    # Invalid: only the form fragment comes back, to be swapped in place.
    assert response.status_code == 422
    body = response.content.decode()
    assert body.lstrip().startswith('<form id="form-articlecreateform"')
    assert "field-danger" in body
    assert "<html" not in body

    response = client.post(url, {"title": "Nouveau", "language": "fr"}, **HX)
    assert response.status_code == 200
    article = Article.objects.get(slug="nouveau")
    assert response["HX-Redirect"] == reverse("edit:editor", args=[article.pk, "fr"])


def test_editor_page(client, editor, translation):
    client.force_login(editor)
    response = client.get(reverse("edit:editor", args=[translation.article_id, "fr"]))
    assert response.status_code == 200
    body = response.content.decode()
    assert 'id="editor-root"' in body
    assert f'"translationId": {translation.pk}' in body


def test_new_translation_page(client, editor, translation):
    client.force_login(editor)
    url = reverse("edit:editor", args=[translation.article_id, "de"])
    response = client.get(url)
    assert response.status_code == 200
    assert "Create this translation" in response.content.decode()
    response = client.post(
        reverse("edit:translation-create", args=[translation.article_id, "de"]),
        {"source": "fr"},
        **HX,
    )
    assert response["HX-Redirect"] == url
    de = ArticleTranslation.objects.get(article=translation.article, language="de")
    assert de.draft_content == translation.draft_content


def test_publish_with_editor_content(client, editor, translation):
    client.force_login(editor)
    url = reverse("edit:publish", args=[translation.article_id, "fr"])
    latest = doc("Version finale")
    response = client.post(
        url,
        {"kind": "update", "note": "", "title": "Guide final", "content": json.dumps(latest)},
        **HX,
    )
    assert response.status_code == 200
    translation.refresh_from_db()
    assert translation.is_published
    assert translation.title == "Guide final"
    assert "Version finale" in translation.html


def test_publish_invalid_kind(client, editor, translation):
    client.force_login(editor)
    url = reverse("edit:publish", args=[translation.article_id, "fr"])
    response = client.post(url, {"kind": "sync"}, **HX)  # sync only offered when outdated
    assert response.status_code == 422


def test_history_and_restore(client, editor, translation):
    content.publish(translation, user=editor)
    content.save_draft(translation, title="Changé", content=doc("Autre"), user=editor)
    content.publish(translation, user=editor)
    client.force_login(editor)
    response = client.get(reverse("edit:history", args=[translation.article_id, "fr"]))
    assert "#2" in response.content.decode()
    response = client.get(reverse("edit:revision", args=[translation.article_id, "fr", 1]))
    assert "Brouillon" in response.content.decode()
    client.post(reverse("edit:revision-restore", args=[translation.article_id, "fr", 1]))
    translation.refresh_from_db()
    assert translation.draft_title == "Guide"


def test_markdown_import_and_export(client, editor, private_collection):
    from django.core.files.uploadedfile import SimpleUploadedFile

    client.force_login(editor)
    upload = SimpleUploadedFile("intro.md", b"# Intro\n\nHello **world**", "text/markdown")
    response = client.post(
        reverse("edit:import", args=["handbook"]),
        {"file": upload, "language": "en", "publish": "on"},
        **HX,
    )
    assert response.status_code == 200
    translation = ArticleTranslation.objects.get(draft_title="Intro")
    assert translation.is_published
    response = client.get(reverse("edit:export", args=[translation.article_id, "en"]))
    assert response["Content-Type"].startswith("text/markdown")
    assert response.content.decode() == "# Intro\n\nHello **world**\n"


def test_article_settings_restrictions_and_move(client, editor, translation, readers):
    other = content.create_article(translation.article.collection, title="Parent", language="fr")
    client.force_login(editor)
    response = client.post(
        reverse("edit:article-settings", args=[translation.article_id]),
        {"slug": "guide-2", "parent": other.article_id, "read_groups": [readers.pk]},
        **HX,
    )
    assert response.status_code == 200
    article = Article.objects.get(pk=translation.article_id)
    assert article.slug == "guide-2"
    assert article.parent_id == other.article_id
    assert list(article.read_groups.all()) == [readers]


def test_delete_article(client, editor, translation):
    client.force_login(editor)
    client.post(reverse("edit:article-delete", args=[translation.article_id]))
    assert not Article.objects.filter(pk=translation.article_id).exists()


def test_admin_pages(client, admin_user, translation):
    client.force_login(admin_user)
    for name in [
        "settings",
        "languages",
        "groups",
        "users",
        "glossary",
        "profile",
        "collection-create",
    ]:
        assert client.get(reverse(f"edit:{name}")).status_code == 200, name
    assert client.get(reverse("edit:collection-permissions", args=["handbook"])).status_code == 200
    assert client.get(reverse("edit:collection-settings", args=["handbook"])).status_code == 200


def test_create_collection_and_grant_role(client, admin_user, editors):
    client.force_login(admin_user)
    response = client.post(
        reverse("edit:collection-create"),
        {"name": "API Reference", "slug": "", "description": "", "icon": "code"},
        **HX,
    )
    assert response.status_code == 200
    collection = Collection.objects.get(slug="api-reference")
    response = client.post(
        reverse("edit:collection-permissions", args=["api-reference"]),
        {"group": editors.pk, "role": "editor"},
        **HX,
    )
    assert collection.roles.get().role == "editor"


def test_reserved_collection_slug(client, admin_user):
    client.force_login(admin_user)
    response = client.post(
        reverse("edit:collection-create"),
        {"name": "Search", "slug": "search", "icon": "book"},
        **HX,
    )
    assert response.status_code == 422


def test_glossary(client, editor, private_collection):
    client.force_login(editor)
    response = client.post(reverse("edit:glossary-create"), {"term_fr": "", "term_de": ""}, **HX)
    assert response.status_code == 422
    response = client.post(
        reverse("edit:glossary-create"),
        {"term_fr": "tableau de bord", "term_en": "dashboard"},
        **HX,
    )
    assert response.status_code == 200
    response = client.get(reverse("edit:glossary"), {"q": "dash"})
    assert "tableau de bord" in response.content.decode()


def test_site_settings_validation(client, admin_user):
    client.force_login(admin_user)
    data = {
        "site_name": "Docs",
        "tagline": "",
        "main_host": "",
        "public_host": "docs.example.com",
        "internal_host": "",
        "edit_host": "",
    }
    response = client.post(reverse("edit:settings"), data, **HX)
    assert response.status_code == 422  # main domain needed
    data["main_host"] = "lorebook.example.com"
    assert client.post(reverse("edit:settings"), data, **HX).status_code == 200


def test_language_toggle_keeps_one(client, admin_user):
    from apps.i18n.models import Language

    client.force_login(admin_user)
    for language in Language.objects.exclude(code="fr"):
        client.post(reverse("edit:language-update", args=[language.pk]), {"action": "toggle"})
    french = Language.objects.get(code="fr")
    client.post(reverse("edit:language-update", args=[french.pk]), {"action": "toggle"})
    assert Language.objects.get(code="fr").enabled
