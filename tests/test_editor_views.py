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
    response = client.post(url, {"title": ""}, **HX)
    # Invalid: only the form fragment comes back, to be swapped in place.
    assert response.status_code == 422
    body = response.content.decode()
    assert body.lstrip().startswith('<form id="form-articlecreateform"')
    assert "field-danger" in body
    assert "<html" not in body

    response = client.post(url, {"title": "Nouveau"}, **HX)
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

    # Imported articles are written in the current language of the user.
    editor.content_language = "en"
    editor.save()
    client.force_login(editor)
    upload = SimpleUploadedFile("intro.md", b"# Intro\n\nHello **world**", "text/markdown")
    response = client.post(
        reverse("edit:import", args=["handbook"]), {"file": upload, "publish": "on"}, **HX
    )
    assert response.status_code == 200
    translation = ArticleTranslation.objects.get(draft_title="Intro")
    assert translation.is_published and translation.language == "en"
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
        "search",
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


def test_glossary_term_delete(client, editor, private_collection):
    from apps.i18n.models import GlossaryTerm

    term = GlossaryTerm.objects.create(translations={"fr": "tableau de bord"})
    client.force_login(editor)
    url = reverse("edit:glossary-edit", args=[term.pk])
    assert "Delete this term" in client.get(url).content.decode()
    response = client.post(url, {"delete": "1"}, **HX)
    assert response["HX-Redirect"] == reverse("edit:glossary")
    assert not GlossaryTerm.objects.exists()


def test_create_article_in_current_language(client, editor, private_collection):
    editor.content_language = "de"
    editor.save()
    client.force_login(editor)
    response = client.post(
        reverse("edit:article-create", args=["handbook"]), {"title": "Neu"}, **HX
    )
    article = Article.objects.get(slug="neu")
    assert response["HX-Redirect"] == reverse("edit:editor", args=[article.pk, "de"])
    assert article.translations.get().language == "de"


def test_create_sub_article_from_the_table(client, editor, translation):
    client.force_login(editor)
    url = reverse("edit:article-create", args=["handbook"])
    response = client.get(url, {"parent": translation.article_id}, **HX)
    body = response.content.decode()
    assert response.status_code == 200
    assert 'id="modal-new-child-article"' in body and "data-autoshow" in body
    assert f'<option value="{translation.article_id}" selected>' in body
    assert client.get(url, {"parent": "x"}, **HX).status_code == 404
    response = client.post(
        f"{url}?child=1", {"title": "Enfant", "parent": translation.article_id}, **HX
    )
    assert response.status_code == 200
    assert Article.objects.get(slug="enfant").parent_id == translation.article_id
    response = client.post(f"{url}?child=1", {"title": ""}, **HX)
    assert response.status_code == 422
    assert 'id="form-child-article"' in response.content.decode()


def test_current_language_follows_the_editor(client, editor, translation):
    client.force_login(editor)
    assert client.get(reverse("edit:article", args=[translation.article_id]))["Location"] == (
        reverse("edit:editor", args=[translation.article_id, "fr"])
    )
    # Opening a language of an article, e.g. from the collection table, switches to it.
    client.get(reverse("edit:editor", args=[translation.article_id, "de"]))
    editor.refresh_from_db()
    assert editor.content_language == "de"
    assert client.get(reverse("edit:article", args=[translation.article_id]))["Location"] == (
        reverse("edit:editor", args=[translation.article_id, "de"])
    )
    response = client.get(reverse("edit:collection", args=["handbook"]))
    assert "your current language" in response.content.decode()


def test_set_language_from_the_sidebar(client, editor, translation):
    client.force_login(editor)
    url = reverse("edit:set-language")
    collection_url = reverse("edit:collection", args=["handbook"])
    response = client.post(url, {"language": "it", "next": collection_url})
    assert response["Location"] == collection_url
    editor.refresh_from_db()
    assert editor.content_language == "it"
    # On an article, the article opens in the new language.
    history_url = reverse("edit:history", args=[translation.article_id, "fr"])
    response = client.post(url, {"language": "en", "next": history_url})
    assert response["Location"] == reverse("edit:editor", args=[translation.article_id, "en"])
    response = client.post(url, {"language": "en", "next": "https://evil.example.com/"})
    assert response["Location"] == reverse("edit:dashboard")
    assert client.post(url, {"language": "xx"}).status_code == 404


def test_search_articles_by_title(client, editor, translation, public_collection):
    content.create_article(public_collection, title="Équipe produit", language="fr")
    # A collection the editor has no role on.
    content.create_article(
        Collection.objects.create(name="Secret", slug="secret"), title="Guide secret", language="fr"
    )
    client.force_login(editor)
    url = reverse("edit:search")
    body = client.get(url, {"q": "guide"}, **HX).content.decode()
    assert "Guide" in body and "Guide secret" not in body
    assert "<html" not in body
    # Accents and case are ignored.
    assert "Équipe produit" in client.get(url, {"q": "equipe"}, **HX).content.decode()
    response = client.get(url, {"q": "nothing like this"})
    assert response.status_code == 200
    assert "No article matches." in response.content.decode()


def test_delete_language(client, admin_user, editor, translation):
    from apps.comments.services import start_thread
    from apps.i18n.models import GlossaryTerm, Language

    collection = translation.article.collection
    both = content.create_article(collection, title="Both", language="fr")
    content.add_translation(both.article, "de")
    german_only = content.create_article(collection, title="Nur Deutsch", language="de")
    child = content.create_article(
        collection, title="Kind", language="fr", parent=german_only.article
    )
    start_thread(both.article.translations.get(language="de"), editor, "Kommentar")
    GlossaryTerm.objects.create(translations={"fr": "bord", "de": "Brett"})
    GlossaryTerm.objects.create(translations={"de": "Nur"})
    editor.content_language = "de"
    editor.save()
    german = Language.objects.get(code="de")

    client.force_login(admin_user)
    url = reverse("edit:language-delete", args=[german.pk])
    response = client.post(url, {f"delete-{german.pk}-confirm": "fr"}, **HX)
    assert response.status_code == 422
    response = client.post(url, {f"delete-{german.pk}-confirm": "de"}, **HX)
    assert response["HX-Redirect"] == reverse("edit:languages")

    assert not Language.objects.filter(code="de").exists()
    assert not ArticleTranslation.objects.filter(language="de").exists()
    assert both.article.translations.count() == 1
    # The German-only article stays: a sub-article still has a translation.
    assert Article.objects.filter(pk=german_only.article_id).exists()
    assert Article.objects.filter(pk=child.article_id).exists()
    assert list(GlossaryTerm.objects.values_list("translations", flat=True)) == [{"fr": "bord"}]
    editor.refresh_from_db()
    assert editor.content_language == ""

    child.article.delete()
    english = Language.objects.get(code="en")
    lonely = content.create_article(collection, title="Alone", language="en")
    client.post(
        reverse("edit:language-delete", args=[english.pk]),
        {f"delete-{english.pk}-confirm": "en"},
        **HX,
    )
    assert not Article.objects.filter(pk=lonely.article_id).exists()


def test_delete_last_enabled_language_refused(client, admin_user):
    from apps.i18n.models import Language

    Language.objects.exclude(code="fr").update(enabled=False)
    french = Language.objects.get(code="fr")
    client.force_login(admin_user)
    response = client.post(
        reverse("edit:language-delete", args=[french.pk]),
        {f"delete-{french.pk}-confirm": "fr"},
        **HX,
    )
    assert response.status_code == 422
    assert Language.objects.filter(code="fr").exists()


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


def test_delete_collection_requires_confirmation(client, admin_user, private_collection):
    client.force_login(admin_user)
    url = reverse("edit:collection-delete", args=["handbook"])
    response = client.post(url, {"delete-confirm": "nope"}, **HX)
    assert response.status_code == 422
    assert Collection.objects.filter(slug="handbook").exists()
    response = client.post(url, {"delete-confirm": "handbook"}, **HX)
    assert response.status_code == 200
    assert not Collection.objects.filter(slug="handbook").exists()


def test_seed_demo(db):
    from django.core.management import call_command

    call_command("seed_demo", admin_password="demo-pass")
    collection = Collection.objects.get(slug="guide")
    assert collection.is_public
    assert (
        ArticleTranslation.objects.published().filter(article__collection=collection).count() == 4
    )
