from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.utils.translation import gettext_lazy as _


def empty_doc() -> dict:
    return {"type": "doc", "content": [{"type": "paragraph"}]}


class Collection(models.Model):
    """A set of articles sharing the same visibility and permissions."""

    name = models.CharField(_("name"), max_length=200)
    slug = models.SlugField(_("slug"), max_length=100, unique=True)
    description = models.TextField(_("description"), blank=True)
    icon = models.CharField(
        _("icon"),
        max_length=64,
        default="book",
        help_text=_("Font Awesome icon name, e.g. book, rocket, gear."),
    )
    is_public = models.BooleanField(
        _("public"),
        default=False,
        help_text=_("Public collections are readable by anyone on the public portal."),
    )
    position = models.PositiveIntegerField(_("position"), default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("collection")
        verbose_name_plural = _("collections")
        ordering = ["position", "name"]

    def __str__(self):
        return self.name


class Article(models.Model):
    """A node of a collection's tree. Any article can hold child articles."""

    collection = models.ForeignKey(
        Collection, on_delete=models.CASCADE, related_name="articles", verbose_name=_("collection")
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
        verbose_name=_("parent"),
    )
    slug = models.SlugField(_("slug"), max_length=120)
    position = models.PositiveIntegerField(_("position"), default=0)
    read_groups = models.ManyToManyField(
        Group,
        blank=True,
        related_name="restricted_articles",
        verbose_name=_("restrict reading to"),
        help_text=_(
            "Leave empty to let every reader of the collection read this article. "
            "Child articles inherit the restriction."
        ),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("article")
        verbose_name_plural = _("articles")
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(fields=["collection", "slug"], name="unique_article_slug")
        ]

    def __str__(self):
        return self.slug

    def ancestors(self) -> list[Article]:
        """Ancestors from the root down to the direct parent."""
        chain = []
        node = self.parent
        seen = {self.pk}
        while node is not None and node.pk not in seen:
            seen.add(node.pk)
            chain.append(node)
            node = node.parent
        return list(reversed(chain))


class TranslationQuerySet(models.QuerySet):
    def published(self):
        return self.filter(published_at__isnull=False)


class ArticleTranslation(models.Model):
    """One language version of an article: its autosaved draft and its published state."""

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="translations")
    language = models.CharField(_("language"), max_length=8)

    # Draft, autosaved by the editor. Readers never see it.
    draft_title = models.CharField(_("title"), max_length=300)
    draft_content = models.JSONField(default=empty_doc)
    draft_updated_at = models.DateTimeField(auto_now_add=True)
    draft_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    has_draft_changes = models.BooleanField(default=True)

    # Published state, replaced as a whole by each publication.
    title = models.CharField(max_length=300, blank=True)
    content = models.JSONField(null=True, blank=True)
    html = models.TextField(blank=True)
    toc = models.JSONField(default=list, blank=True)
    text = models.TextField(blank=True)
    renderer_version = models.PositiveIntegerField(default=0)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    is_outdated = models.BooleanField(_("outdated"), default=False)

    search_vector = SearchVectorField(null=True, editable=False)

    objects = TranslationQuerySet.as_manager()

    class Meta:
        verbose_name = _("article translation")
        verbose_name_plural = _("article translations")
        constraints = [
            models.UniqueConstraint(fields=["article", "language"], name="unique_article_language")
        ]
        indexes = [
            GinIndex(fields=["search_vector"], name="translation_search_idx"),
            GinIndex(
                fields=["title"], name="translation_title_trgm_idx", opclasses=["gin_trgm_ops"]
            ),
        ]

    def __str__(self):
        return f"{self.display_title} [{self.language}]"

    @property
    def is_published(self) -> bool:
        return self.published_at is not None

    @property
    def display_title(self) -> str:
        return self.title or self.draft_title

    @property
    def status(self) -> str:
        if not self.is_published:
            return "draft"
        if self.is_outdated:
            return "outdated"
        return "published"


class Revision(models.Model):
    """A published state of a translation, kept in its history."""

    class Kind(models.TextChoices):
        UPDATE = "update", _("Content update")
        MINOR = "minor", _("Minor change")
        SYNC = "sync", _("Translation synchronised")

    translation = models.ForeignKey(
        ArticleTranslation, on_delete=models.CASCADE, related_name="revisions"
    )
    number = models.PositiveIntegerField()
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.UPDATE)
    title = models.CharField(max_length=300)
    content = models.JSONField()
    note = models.CharField(_("note"), max_length=300, blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("revision")
        verbose_name_plural = _("revisions")
        ordering = ["-number"]
        constraints = [
            models.UniqueConstraint(fields=["translation", "number"], name="unique_revision_number")
        ]

    def __str__(self):
        return f"{self.translation} #{self.number}"
