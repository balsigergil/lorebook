"""Read and write rights.

Groups receive a role on a collection (reader < editor < admin). Instance
administrators hold every role. Reading can be further restricted per
article to some groups, and the restriction applies to the whole subtree.

Two portals expose content to readers:
- PUBLIC: anonymous, public collections only, restricted articles hidden.
- INTERNAL: signed-in users, collections where they hold a role, plus the
  public collections.
"""

from typing import Literal

from django.contrib.auth.models import Group
from django.db.models import QuerySet

from apps.content.models import Article, Collection

from .models import ROLE_RANK, CollectionRole, Role

Portal = Literal["public", "internal"]
PUBLIC: Portal = "public"
INTERNAL: Portal = "internal"


def is_authenticated(user) -> bool:
    return bool(user and user.is_authenticated and user.is_active)


def is_instance_admin(user) -> bool:
    return is_authenticated(user) and user.is_superuser


def user_group_ids(user) -> frozenset[int]:
    if not is_authenticated(user):
        return frozenset()
    cached = getattr(user, "_lorebook_group_ids", None)
    if cached is None:
        cached = frozenset(user.groups.values_list("id", flat=True))
        user._lorebook_group_ids = cached
    return cached


def _roles_by_collection(user) -> dict[int, str]:
    """Highest role the user holds on each collection, from their groups."""
    if not is_authenticated(user):
        return {}
    cached = getattr(user, "_lorebook_roles", None)
    if cached is None:
        cached = {}
        rows = CollectionRole.objects.filter(group_id__in=user_group_ids(user)).values_list(
            "collection_id", "role"
        )
        for collection_id, role in rows:
            if ROLE_RANK[role] > ROLE_RANK.get(cached.get(collection_id), 0):
                cached[collection_id] = role
        user._lorebook_roles = cached
    return cached


def collection_role(user, collection: Collection) -> str | None:
    if is_instance_admin(user):
        return Role.ADMIN
    return _roles_by_collection(user).get(collection.pk)


def has_role(user, collection: Collection, role: str) -> bool:
    current = collection_role(user, collection)
    return current is not None and ROLE_RANK[current] >= ROLE_RANK[role]


def can_edit_collection(user, collection: Collection) -> bool:
    return has_role(user, collection, Role.EDITOR)


def can_admin_collection(user, collection: Collection) -> bool:
    return has_role(user, collection, Role.ADMIN)


def is_editor_somewhere(user) -> bool:
    if is_instance_admin(user):
        return True
    return any(
        ROLE_RANK[role] >= ROLE_RANK[Role.EDITOR] for role in _roles_by_collection(user).values()
    )


def can_read_collection(user, collection: Collection, portal: Portal) -> bool:
    if portal == PUBLIC:
        return collection.is_public
    if not is_authenticated(user):
        return False
    return collection.is_public or collection_role(user, collection) is not None


def readable_collections(user, portal: Portal) -> QuerySet[Collection]:
    collections = Collection.objects.all()
    if portal == PUBLIC:
        return collections.filter(is_public=True)
    if not is_authenticated(user):
        return collections.none()
    if is_instance_admin(user):
        return collections
    ids = set(_roles_by_collection(user))
    return collections.filter(is_public=True) | collections.filter(pk__in=ids)


def editable_collections(user) -> QuerySet[Collection]:
    if is_instance_admin(user):
        return Collection.objects.all()
    ids = [
        collection_id
        for collection_id, role in _roles_by_collection(user).items()
        if ROLE_RANK[role] >= ROLE_RANK[Role.EDITOR]
    ]
    return Collection.objects.filter(pk__in=ids)


def restrictions_for(article_ids) -> dict[int, frozenset[int]]:
    """Map article id -> ids of the groups allowed to read it (restricted articles only)."""
    through = Article.read_groups.through
    result: dict[int, set[int]] = {}
    for article_id, group_id in through.objects.filter(article_id__in=article_ids).values_list(
        "article_id", "group_id"
    ):
        result.setdefault(article_id, set()).add(group_id)
    return {key: frozenset(value) for key, value in result.items()}


def readable_article_ids(
    user, collection: Collection, portal: Portal, articles: list[Article] | None = None
) -> set[int]:
    """Ids of the collection's articles the user can read on the given portal."""
    if not can_read_collection(user, collection, portal):
        return set()
    if articles is None:
        articles = list(collection.articles.only("id", "parent_id"))
    ids = {article.pk for article in articles}
    if portal == INTERNAL and can_edit_collection(user, collection):
        return ids
    parents = {article.pk: article.parent_id for article in articles}
    restrictions = restrictions_for(ids)
    groups = user_group_ids(user) if portal == INTERNAL else frozenset()
    memo: dict[int, bool] = {}

    def allowed(article_id: int, depth: int = 0) -> bool:
        if article_id in memo:
            return memo[article_id]
        if depth > 200:  # corrupted tree (cycle): fail closed
            return False
        restriction = restrictions.get(article_id)
        result = not restriction or bool(restriction & groups)
        parent_id = parents.get(article_id)
        if result and parent_id is not None:
            result = allowed(parent_id, depth + 1)
        memo[article_id] = result
        return result

    return {article_id for article_id in ids if allowed(article_id)}


def can_read_article(user, article: Article, portal: Portal) -> bool:
    collection = article.collection
    if not can_read_collection(user, collection, portal):
        return False
    if portal == INTERNAL and can_edit_collection(user, collection):
        return True
    chain = [*article.ancestors(), article]
    restrictions = restrictions_for([node.pk for node in chain])
    if not restrictions:
        return True
    if portal == PUBLIC:
        return False
    groups = user_group_ids(user)
    return all(bool(restriction & groups) for restriction in restrictions.values())


def readable_article_ids_everywhere(user, portal: Portal) -> set[int]:
    result: set[int] = set()
    for collection in readable_collections(user, portal):
        result |= readable_article_ids(user, collection, portal)
    return result


def inherited_restrictions(article: Article) -> list[tuple[Article, list[Group]]]:
    """Restricted ancestors of an article with the groups each one allows."""
    result = []
    for node in article.ancestors():
        groups = list(node.read_groups.all())
        if groups:
            result.append((node, groups))
    return result
