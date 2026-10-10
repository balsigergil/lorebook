import pytest

from apps.content import services as content
from apps.content.models import ArticleTranslation, Revision

from .conftest import doc


@pytest.fixture
def article(private_collection, editor):
    fr = content.create_article(
        private_collection, title="Bonjour", language="fr", content=doc("Texte"), user=editor
    )
    content.publish(fr, user=editor)
    de = content.add_translation(fr.article, "de", user=editor, copy_from=fr)
    content.save_draft(de, title="Hallo", content=doc("Text"), user=editor)
    content.publish(de, user=editor, kind="sync")
    return fr.article


def get(article, language) -> ArticleTranslation:
    return ArticleTranslation.objects.get(article=article, language=language)


def test_publish_copies_draft_and_records_revision(
    private_collection, editor, django_capture_on_commit_callbacks
):
    translation = content.create_article(
        private_collection, title="Titre", language="fr", content=doc("Un"), user=editor
    )
    assert not translation.is_published
    with django_capture_on_commit_callbacks(execute=True):
        revision = content.publish(translation, user=editor, note="first")
    translation.refresh_from_db()
    assert translation.is_published
    assert translation.title == "Titre"
    assert "<p>Un</p>" in translation.html
    assert translation.text == "Un"
    assert not translation.has_draft_changes
    assert revision.number == 1 and revision.note == "first"
    assert translation.search_vector is not None  # indexed by the task

    content.save_draft(translation, title="Titre 2", content=doc("Deux"), user=editor)
    translation.refresh_from_db()
    # Readers keep seeing the published version while the draft changes.
    assert translation.title == "Titre" and "Un" in translation.html
    assert translation.has_draft_changes
    content.publish(translation, user=editor)
    assert translation.revisions.count() == 2


def test_update_marks_other_languages_outdated(article, editor):
    assert not get(article, "fr").is_outdated
    assert not get(article, "de").is_outdated

    content.publish(get(article, "fr"), user=editor, kind="update")
    assert not get(article, "fr").is_outdated
    assert get(article, "de").is_outdated


def test_minor_change_marks_nothing(article, editor):
    content.publish(get(article, "fr"), user=editor, kind="minor")
    assert not get(article, "de").is_outdated
    assert Revision.objects.filter(translation=get(article, "fr"), kind="minor").exists()


def test_sync_brings_version_up_to_date_without_touching_others(article, editor):
    content.publish(get(article, "fr"), user=editor, kind="update")
    assert get(article, "de").is_outdated

    # Publishing the outdated version as a plain minor change keeps it outdated.
    content.publish(get(article, "de"), user=editor, kind="minor")
    assert get(article, "de").is_outdated

    content.publish(get(article, "de"), user=editor, kind="sync")
    assert not get(article, "de").is_outdated
    assert not get(article, "fr").is_outdated


def test_restore_revision_loads_draft(article, editor):
    fr = get(article, "fr")
    content.save_draft(fr, title="Nouveau", content=doc("Nouveau texte"), user=editor)
    content.publish(fr, user=editor)
    first = fr.revisions.get(number=1)
    content.restore_revision(first, user=editor)
    fr.refresh_from_db()
    assert fr.draft_title == "Bonjour"
    assert fr.title == "Nouveau"  # still live until published
    assert fr.has_draft_changes


def test_pick_published_rules(article, editor):
    translations = list(article.translations.all())
    assert content.pick_published(translations, "fr").situation == "current"

    content.publish(get(article, "fr"), user=editor, kind="update")
    translations = list(article.translations.all())
    outdated = content.pick_published(translations, "de")
    assert outdated.situation == "outdated"
    assert outdated.translation.language == "de"
    assert outdated.up_to_date.language == "fr"

    missing = content.pick_published(translations, "it")
    assert missing.situation == "missing"
    assert missing.translation.language == "fr"  # most recently published


def test_unpublished_translations_are_never_shown(private_collection, editor):
    translation = content.create_article(private_collection, title="Draft", language="fr")
    assert content.pick_published([translation], "fr") is None


def test_move_article(private_collection, editor):
    a = content.create_article(private_collection, title="A", language="fr").article
    b = content.create_article(private_collection, title="B", language="fr").article
    c = content.create_article(private_collection, title="C", language="fr", parent=a).article
    content.move_article(b, a, 0)
    b.refresh_from_db()
    c.refresh_from_db()
    assert b.parent == a and b.position == 0 and c.position == 1
    with pytest.raises(content.ContentError):
        content.move_article(a, c)


def test_build_tree(private_collection):
    a = content.create_article(private_collection, title="A", language="fr").article
    content.create_article(private_collection, title="A1", language="fr", parent=a)
    content.create_article(private_collection, title="B", language="fr")
    articles = list(private_collection.articles.all())
    titles = content.translations_for_display(articles, "fr", published_only=False)
    tree = content.build_tree(articles, titles)
    assert [node.title for node in tree] == ["A", "B"]
    assert [node.title for node in tree[0].children] == ["A1"]
    hidden = content.build_tree(articles, titles, include=lambda article: article.pk != a.pk)
    assert [node.title for node in hidden] == ["B"]
