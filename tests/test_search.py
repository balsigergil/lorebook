import pytest
from django.contrib.auth.models import AnonymousUser

from apps.access import services as access
from apps.content import services as content
from apps.search import services as search

from .conftest import doc


@pytest.fixture
def indexed(public_collection, private_collection, editor, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        fr = content.create_article(
            public_collection,
            title="Configurer l'éléphant",
            language="fr",
            content=doc("Les éléphants mangent des bananes dans la configuration."),
        )
        content.publish(fr)
        en = content.add_translation(fr.article, "en")
        content.save_draft(
            en, title="Configure the elephant", content=doc("Elephants eat bananas.")
        )
        content.publish(en, kind="sync")
        secret = content.create_article(
            private_collection,
            title="Salaires",
            language="fr",
            content=doc("Les éléphants secrets du service RH."),
        )
        content.publish(secret)
    return fr, en, secret


def test_stemming_and_accents(indexed):
    fr, _en, _secret = indexed
    ids = {fr.article_id}
    hits = search.search("elephant", language="fr", article_ids=ids)
    assert [hit.article_id for hit in hits] == [fr.article_id]
    # One hit per article, in the reader's language when possible.
    assert hits[0].language == "fr"
    assert "<mark>" in hits[0].snippet
    english = search.search("elephant", language="en", article_ids=ids)
    assert english[0].language == "en"


def test_typo_tolerance_on_titles(indexed):
    fr, _en, _secret = indexed
    hits = search.search("configuer", language="fr", article_ids={fr.article_id})
    assert hits and hits[0].article_id == fr.article_id


def test_results_filtered_by_rights(indexed, reader):
    fr, _en, secret = indexed
    public_ids = access.readable_article_ids_everywhere(AnonymousUser(), access.PUBLIC)
    hits = search.search("éléphants", language="fr", article_ids=public_ids)
    assert {hit.article_id for hit in hits} == {fr.article_id}
    internal_ids = access.readable_article_ids_everywhere(reader, access.INTERNAL)
    hits = search.search("éléphants", language="fr", article_ids=internal_ids)
    assert {hit.article_id for hit in hits} == {fr.article_id, secret.article_id}


def test_snippet_is_escaped(public_collection, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        translation = content.create_article(
            public_collection, title="XSS", language="en", content=doc("<b>giraffe</b> danger")
        )
        content.publish(translation)
    hits = search.search("giraffe", language="en", article_ids={translation.article_id})
    assert "<b>" not in hits[0].snippet
    assert hits[0].snippet.startswith("<mark>giraffe</mark>")


def test_unpublished_are_not_found(public_collection, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        translation = content.create_article(
            public_collection, title="Zebra", language="en", content=doc("zebra")
        )
        content.publish(translation)
        content.unpublish(translation)
    assert search.search("zebra", language="en", article_ids={translation.article_id}) == []
