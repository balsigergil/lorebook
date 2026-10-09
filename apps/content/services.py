"""Business logic of the content: articles, drafts, publication, history."""

from dataclasses import dataclass, field
from typing import Literal

from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.text import slugify

from .models import Article, ArticleTranslation, Collection, Revision, empty_doc
from .rendering import RENDERER_VERSION, render_document

PublishKind = Literal["update", "minor", "sync"]


class ContentError(Exception):
    pass


# Collections and articles


def unique_slug(queryset, base: str, field_name: str = "slug", exclude_pk=None) -> str:
    base = slugify(base)[:90] or "untitled"
    candidate = base
    counter = 2
    existing = queryset
    if exclude_pk is not None:
        existing = existing.exclude(pk=exclude_pk)
    while existing.filter(**{field_name: candidate}).exists():
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate


def next_position(collection: Collection, parent: Article | None) -> int:
    current = collection.articles.filter(parent=parent).aggregate(value=Max("position"))["value"]
    return 0 if current is None else current + 1


@transaction.atomic
def create_article(
    collection: Collection,
    *,
    title: str,
    language: str,
    user=None,
    parent: Article | None = None,
    content: dict | None = None,
    slug: str = "",
) -> ArticleTranslation:
    if parent is not None and parent.collection_id != collection.pk:
        raise ContentError("The parent article belongs to another collection.")
    article = Article.objects.create(
        collection=collection,
        parent=parent,
        slug=unique_slug(collection.articles.all(), slug or title),
        position=next_position(collection, parent),
        created_by=user,
    )
    return ArticleTranslation.objects.create(
        article=article,
        language=language,
        draft_title=title,
        draft_content=content or empty_doc(),
        draft_updated_by=user,
    )


@transaction.atomic
def add_translation(
    article: Article, language: str, user=None, copy_from: ArticleTranslation | None = None
) -> ArticleTranslation:
    translation, created = ArticleTranslation.objects.get_or_create(
        article=article,
        language=language,
        defaults={
            "draft_title": copy_from.display_title if copy_from else article.slug,
            "draft_content": (
                (copy_from.content or copy_from.draft_content) if copy_from else empty_doc()
            ),
            "draft_updated_by": user,
        },
    )
    return translation


def save_draft(translation: ArticleTranslation, *, title: str, content: dict, user=None):
    translation.draft_title = title.strip()[:300] or translation.draft_title
    translation.draft_content = content
    translation.draft_updated_at = timezone.now()
    translation.draft_updated_by = user
    translation.has_draft_changes = True
    translation.save(
        update_fields=[
            "draft_title",
            "draft_content",
            "draft_updated_at",
            "draft_updated_by",
            "has_draft_changes",
        ]
    )


def render_into(translation: ArticleTranslation, content: dict) -> None:
    result = render_document(content)
    translation.html = result.html
    translation.toc = result.toc
    translation.text = result.text
    translation.renderer_version = RENDERER_VERSION


def ensure_rendered(translation: ArticleTranslation) -> ArticleTranslation:
    """Re-render the stored HTML when the renderer changed since publication."""
    if translation.is_published and translation.renderer_version != RENDERER_VERSION:
        render_into(translation, translation.content)
        ArticleTranslation.objects.filter(pk=translation.pk).update(
            html=translation.html,
            toc=translation.toc,
            text=translation.text,
            renderer_version=translation.renderer_version,
        )
    return translation


@transaction.atomic
def publish(
    translation: ArticleTranslation, *, user=None, kind: PublishKind = "update", note: str = ""
) -> Revision:
    """Replace the published version with the draft and record a revision.

    - update: the other published languages become outdated.
    - minor: typo or formatting; no other version changes status.
    - sync: the version is declared in sync with the others again.
    """
    translation = ArticleTranslation.objects.select_for_update().get(pk=translation.pk)
    if kind == "sync" and not translation.is_outdated:
        kind = "minor"

    now = timezone.now()
    translation.title = translation.draft_title
    translation.content = translation.draft_content
    render_into(translation, translation.content)
    translation.published_at = now
    translation.published_by = user
    translation.has_draft_changes = False
    if kind in ("update", "sync"):
        translation.is_outdated = False
    translation.save()

    if kind == "update":
        (
            ArticleTranslation.objects.published()
            .filter(article_id=translation.article_id)
            .exclude(pk=translation.pk)
            .update(is_outdated=True)
        )

    number = (translation.revisions.aggregate(value=Max("number"))["value"] or 0) + 1
    revision = Revision.objects.create(
        translation=translation,
        number=number,
        kind=kind,
        title=translation.title,
        content=translation.content,
        note=note[:300],
        author=user,
    )
    Article.objects.filter(pk=translation.article_id).update(updated_at=now)

    from apps.search.tasks import index_translation

    transaction.on_commit(lambda: index_translation.enqueue(translation.pk))
    return revision


def restore_revision(revision: Revision, user=None) -> ArticleTranslation:
    """Load a revision into the draft. Publishing it makes it live again."""
    translation = revision.translation
    save_draft(translation, title=revision.title, content=revision.content, user=user)
    return translation


@transaction.atomic
def unpublish(translation: ArticleTranslation) -> None:
    translation.published_at = None
    translation.has_draft_changes = True
    translation.is_outdated = False
    translation.search_vector = None
    translation.save(
        update_fields=["published_at", "has_draft_changes", "is_outdated", "search_vector"]
    )


def descendant_ids(article: Article) -> set[int]:
    pairs = list(article.collection.articles.values_list("id", "parent_id"))
    children: dict[int | None, list[int]] = {}
    for article_id, parent_id in pairs:
        children.setdefault(parent_id, []).append(article_id)
    result: set[int] = set()
    stack = list(children.get(article.pk, []))
    while stack:
        current = stack.pop()
        if current in result:
            continue
        result.add(current)
        stack.extend(children.get(current, []))
    return result


@transaction.atomic
def move_article(article: Article, parent: Article | None, position: int | None = None) -> None:
    if parent is not None:
        if parent.collection_id != article.collection_id:
            raise ContentError("An article can only move inside its collection.")
        if parent.pk == article.pk or parent.pk in descendant_ids(article):
            raise ContentError("An article cannot be moved under itself.")
    siblings = list(
        article.collection.articles.filter(parent=parent)
        .exclude(pk=article.pk)
        .order_by("position", "id")
    )
    if position is None or position > len(siblings):
        position = len(siblings)
    siblings.insert(max(position, 0), article)
    article.parent = parent
    for index, sibling in enumerate(siblings):
        sibling.position = index
        if sibling.pk == article.pk:
            sibling.parent = parent
    Article.objects.bulk_update(siblings, ["position", "parent"])


# Reading


@dataclass
class TreeNode:
    article: Article
    translation: ArticleTranslation | None
    children: list[TreeNode] = field(default_factory=list)

    @property
    def title(self) -> str:
        if self.translation is None:
            return self.article.slug
        return self.translation.display_title


def build_tree(
    articles: list[Article],
    translations: dict[int, ArticleTranslation | None],
    include=None,
) -> list[TreeNode]:
    """Nest articles under their parents. `include` filters the nodes kept;
    a filtered-out article hides its whole subtree."""
    nodes = {
        article.pk: TreeNode(article, translations.get(article.pk))
        for article in articles
        if include is None or include(article)
    }
    roots = []
    for article in sorted(articles, key=lambda item: (item.position, item.pk)):
        node = nodes.get(article.pk)
        if node is None:
            continue
        if article.parent_id is None:
            roots.append(node)
        elif article.parent_id in nodes:
            nodes[article.parent_id].children.append(node)
    return roots


def flatten(tree: list[TreeNode]) -> list[TreeNode]:
    result = []
    for node in tree:
        result.append(node)
        result.extend(flatten(node.children))
    return result


Situation = Literal["current", "outdated", "missing"]


@dataclass
class ReaderVersion:
    translation: ArticleTranslation
    situation: Situation
    up_to_date: ArticleTranslation | None = None


def pick_published(translations: list[ArticleTranslation], language: str) -> ReaderVersion | None:
    """Choose the published version shown to a reader of `language`.

    - up-to-date version in the reader's language: shown as is;
    - outdated version in the reader's language: shown, with a link to the
      most recent up-to-date version;
    - no version in that language: the most recently published one.
    """
    published = [item for item in translations if item.is_published]
    if not published:
        return None
    by_recency = sorted(published, key=lambda item: item.published_at, reverse=True)
    for item in published:
        if item.language == language:
            if not item.is_outdated:
                return ReaderVersion(item, "current")
            up_to_date = next((other for other in by_recency if not other.is_outdated), None)
            return ReaderVersion(item, "outdated", up_to_date)
    return ReaderVersion(by_recency[0], "missing")


def translations_for_display(
    articles: list[Article], language: str, published_only: bool
) -> dict[int, ArticleTranslation | None]:
    """For each article, the translation used for its title in navigation."""
    grouped: dict[int, list[ArticleTranslation]] = {}
    queryset = ArticleTranslation.objects.filter(article__in=articles).defer(
        "draft_content", "content", "html", "text", "search_vector"
    )
    if published_only:
        queryset = queryset.published()
    for translation in queryset:
        grouped.setdefault(translation.article_id, []).append(translation)
    result: dict[int, ArticleTranslation | None] = {}
    for article in articles:
        items = grouped.get(article.pk, [])
        if published_only:
            picked = pick_published(items, language)
            result[article.pk] = picked.translation if picked else None
        else:
            result[article.pk] = next(
                (item for item in items if item.language == language), items[0] if items else None
            )
    return result
