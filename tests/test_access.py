import pytest
from django.contrib.auth.models import AnonymousUser, Group

from apps.access import services as access
from apps.access.models import CollectionRole, Role
from apps.content import services as content


@pytest.fixture
def tree(private_collection, editor):
    root = content.create_article(
        private_collection, title="Root", language="fr", user=editor
    ).article
    child = content.create_article(
        private_collection, title="Child", language="fr", parent=root, user=editor
    ).article
    grandchild = content.create_article(
        private_collection, title="Grandchild", language="fr", parent=child, user=editor
    ).article
    return root, child, grandchild


def test_roles(private_collection, admin_user, editor, reader, outsider):
    assert access.collection_role(admin_user, private_collection) == Role.ADMIN
    assert access.collection_role(editor, private_collection) == Role.EDITOR
    assert access.collection_role(reader, private_collection) == Role.READER
    assert access.collection_role(outsider, private_collection) is None
    assert access.can_edit_collection(editor, private_collection)
    assert not access.can_edit_collection(reader, private_collection)
    assert not access.can_admin_collection(editor, private_collection)
    assert access.is_editor_somewhere(editor)
    assert not access.is_editor_somewhere(reader)


def test_highest_role_wins(private_collection, reader, editors):
    reader.groups.add(editors)
    reader = type(reader).objects.get(pk=reader.pk)
    assert access.collection_role(reader, private_collection) == Role.EDITOR


def test_collection_visibility(private_collection, public_collection, reader, outsider):
    anonymous = AnonymousUser()
    assert list(access.readable_collections(anonymous, access.PUBLIC)) == [public_collection]
    assert list(access.readable_collections(anonymous, access.INTERNAL)) == []
    assert set(access.readable_collections(reader, access.INTERNAL)) == {
        private_collection,
        public_collection,
    }
    assert list(access.readable_collections(outsider, access.INTERNAL)) == [public_collection]
    assert not access.can_read_collection(reader, private_collection, access.PUBLIC)


def test_restrictions_are_inherited(tree, private_collection, reader, editor):
    root, child, grandchild = tree
    managers = Group.objects.create(name="Managers")
    child.read_groups.add(managers)

    assert access.can_read_article(reader, root, access.INTERNAL)
    assert not access.can_read_article(reader, child, access.INTERNAL)
    assert not access.can_read_article(reader, grandchild, access.INTERNAL)
    assert access.readable_article_ids(reader, private_collection, access.INTERNAL) == {root.pk}
    # Editors bypass read restrictions in their collections.
    assert access.can_read_article(editor, grandchild, access.INTERNAL)

    reader.groups.add(managers)
    reader = type(reader).objects.get(pk=reader.pk)
    assert access.can_read_article(reader, grandchild, access.INTERNAL)
    assert access.readable_article_ids(reader, private_collection, access.INTERNAL) == {
        root.pk,
        child.pk,
        grandchild.pk,
    }


def test_every_restriction_level_must_be_satisfied(tree, reader, readers):
    root, child, grandchild = tree
    managers = Group.objects.create(name="Managers")
    root.read_groups.add(readers)
    grandchild.read_groups.add(managers)
    assert access.can_read_article(reader, child, access.INTERNAL)
    assert not access.can_read_article(reader, grandchild, access.INTERNAL)


def test_restricted_articles_are_hidden_on_the_public_portal(public_collection, editor, readers):
    article = content.create_article(public_collection, title="Secret", language="fr").article
    open_article = content.create_article(public_collection, title="Open", language="fr").article
    article.read_groups.add(readers)
    anonymous = AnonymousUser()
    assert not access.can_read_article(anonymous, article, access.PUBLIC)
    assert access.readable_article_ids(anonymous, public_collection, access.PUBLIC) == {
        open_article.pk
    }


def test_admin_role_from_group(private_collection, outsider):
    admins = Group.objects.create(name="Owners")
    CollectionRole.objects.create(collection=private_collection, group=admins, role=Role.ADMIN)
    outsider.groups.add(admins)
    assert access.can_admin_collection(outsider, private_collection)
