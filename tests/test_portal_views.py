import pytest
from django.urls import reverse

from apps.content import services as content

from .conftest import doc

BROWSER = "Mozilla/5.0 (X11; Linux x86_64) Chrome/140 Safari/537.36"


def public_url(name, *args):
    return reverse(f"portal:{name}", args=args, current_app="public")


def internal_url(name, *args):
    return reverse(f"portal:{name}", args=args, current_app="internal")


def test_urls_per_portal():
    assert public_url("home-lang", "fr") == "/fr/"
    assert internal_url("home-lang", "fr") == "/internal/fr/"


def test_root_negotiates_language(client, db):
    response = client.get("/", HTTP_ACCEPT_LANGUAGE="de-CH,de;q=0.9,en;q=0.5")
    assert response.status_code == 302
    assert response["Location"] == "/de/"
    response = client.get("/", HTTP_ACCEPT_LANGUAGE="ja")
    assert response["Location"] == "/fr/"  # first enabled language


def test_disabled_language_is_404(client, db):
    assert client.get("/xx/").status_code == 404


def test_public_article(client, published):
    url = public_url("article", "fr", "docs", published.article.slug)
    response = client.get(url, HTTP_USER_AGENT=BROWSER)
    assert response.status_code == 200
    body = response.content.decode()
    assert "Bienvenue" in body
    assert "Le guide de démarrage" in body
    assert "comments-placeholder" not in body  # never on the public portal
    assert published.article.daily_views.get().views == 1


def test_missing_language_banner(client, published):
    url = public_url("article", "de", "docs", published.article.slug)
    response = client.get(url)
    assert response.status_code == 200
    assert "Not yet available in Deutsch" in response.content.decode()


def test_outdated_banner(client, published, editor):
    de = content.add_translation(published.article, "de", copy_from=published)
    content.publish(de, kind="sync")
    content.publish(published, kind="update")
    response = client.get(public_url("article", "de", "docs", published.article.slug))
    body = response.content.decode()
    assert "This version is not up to date." in body
    assert public_url("article", "fr", "docs", published.article.slug) in body


def test_private_collection_hidden_from_public(client, private_collection, editor):
    translation = content.create_article(private_collection, title="Interne", language="fr")
    content.publish(translation)
    assert client.get(public_url("collection", "fr", "handbook")).status_code == 404
    url = public_url("article", "fr", "handbook", translation.article.slug)
    assert client.get(url).status_code == 404


def test_internal_requires_login(client, published):
    response = client.get(internal_url("home-lang", "fr"))
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


def test_internal_portal_shows_private_and_public(client, reader, published, private_collection):
    translation = content.create_article(private_collection, title="Interne", language="fr")
    content.publish(translation)
    client.force_login(reader)
    response = client.get(internal_url("home-lang", "fr"))
    body = response.content.decode()
    assert "Handbook" in body and "Docs" in body
    response = client.get(internal_url("article", "fr", "handbook", translation.article.slug))
    assert response.status_code == 200
    assert "comments-placeholder" in response.content.decode()


def test_outsider_cannot_read_private(client, outsider, private_collection):
    translation = content.create_article(private_collection, title="Interne", language="fr")
    content.publish(translation)
    client.force_login(outsider)
    url = internal_url("article", "fr", "handbook", translation.article.slug)
    assert client.get(url).status_code == 404


def test_navigation_hides_drafts(client, public_collection, published):
    content.create_article(public_collection, title="Brouillon secret", language="fr")
    response = client.get(public_url("collection", "fr", "docs"))
    body = response.content.decode()
    assert "Bienvenue" in body
    assert "Brouillon secret" not in body


def test_search_page(client, public_collection, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        translation = content.create_article(
            public_collection,
            title="Installation",
            language="fr",
            content=doc("Installer la girafe"),
        )
        content.publish(translation)
    response = client.get(public_url("search", "fr"), {"q": "girafe"})
    assert "Installation" in response.content.decode()
    partial = client.get(
        public_url("search", "fr"),
        {"q": "girafe"},
        HTTP_HX_REQUEST="true",
        HTTP_HX_REQUEST_TYPE="partial",
    )
    body = partial.content.decode()
    assert body.lstrip().startswith('<div id="search-results"')
    assert "Installation" in body


def test_most_read_on_home(client, published):
    client.get(public_url("article", "fr", "docs", published.article.slug), HTTP_USER_AGENT=BROWSER)
    response = client.get(public_url("home-lang", "fr"))
    assert "Most read" in response.content.decode()


@pytest.mark.parametrize("path", ["/healthz", "/accounts/login/"])
def test_misc_pages(client, db, path):
    assert client.get(path).status_code == 200
