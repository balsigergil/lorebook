import pytest
from django.contrib.auth.models import Group

from apps.access.models import CollectionRole, Role, User
from apps.content import services as content
from apps.content.models import Collection


def doc(*paragraphs: str) -> dict:
    return {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": text}]}
            for text in paragraphs
        ],
    }


@pytest.fixture(autouse=True)
def _clear_caches():
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser("admin@example.com", "pass", first_name="Ada")


@pytest.fixture
def editors(db):
    return Group.objects.create(name="Editors")


@pytest.fixture
def readers(db):
    return Group.objects.create(name="Readers")


@pytest.fixture
def editor(db, editors):
    user = User.objects.create_user("editor@example.com", "pass", first_name="Eddie")
    user.groups.add(editors)
    return user


@pytest.fixture
def reader(db, readers):
    user = User.objects.create_user("reader@example.com", "pass", first_name="Rita")
    user.groups.add(readers)
    return user


@pytest.fixture
def outsider(db):
    return User.objects.create_user("outsider@example.com", "pass")


@pytest.fixture
def private_collection(db, editors, readers):
    collection = Collection.objects.create(name="Handbook", slug="handbook")
    CollectionRole.objects.create(collection=collection, group=editors, role=Role.EDITOR)
    CollectionRole.objects.create(collection=collection, group=readers, role=Role.READER)
    return collection


@pytest.fixture
def public_collection(db, editors):
    collection = Collection.objects.create(name="Docs", slug="docs", is_public=True)
    CollectionRole.objects.create(collection=collection, group=editors, role=Role.EDITOR)
    return collection


@pytest.fixture
def published(public_collection, editor):
    """A public article published in French."""
    translation = content.create_article(
        public_collection,
        title="Bienvenue",
        language="fr",
        content=doc("Le guide de démarrage des éléphants."),
        user=editor,
    )
    content.publish(translation, user=editor)
    translation.refresh_from_db()
    return translation
