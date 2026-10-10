from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

# Languages Lorebook knows how to index: code -> (native name, PostgreSQL
# text search configuration created by the search app's migrations).
KNOWN_LANGUAGES = {
    "fr": ("Français", "lorebook_fr"),
    "de": ("Deutsch", "lorebook_de"),
    "it": ("Italiano", "lorebook_it"),
    "en": ("English", "lorebook_en"),
    "es": ("Español", "lorebook_es"),
    "pt": ("Português", "lorebook_pt"),
    "nl": ("Nederlands", "lorebook_nl"),
    "rm": ("Rumantsch", "lorebook_simple"),
}


class LanguageQuerySet(models.QuerySet):
    def enabled(self):
        return self.filter(enabled=True)


class Language(models.Model):
    """A content language. Enabled languages apply to every collection."""

    code = models.CharField(
        _("code"),
        max_length=8,
        unique=True,
        choices=[(code, name) for code, (name, _config) in KNOWN_LANGUAGES.items()],
    )
    name = models.CharField(_("name"), max_length=64)
    enabled = models.BooleanField(_("enabled"), default=True)
    position = models.PositiveIntegerField(_("position"), default=0)

    objects = LanguageQuerySet.as_manager()

    class Meta:
        verbose_name = _("language")
        verbose_name_plural = _("languages")
        ordering = ["position", "code"]

    def __str__(self):
        return self.name

    @property
    def search_config(self) -> str:
        return KNOWN_LANGUAGES.get(self.code, ("", "lorebook_simple"))[1]


class GlossaryTerm(models.Model):
    """An entry of the instance-wide glossary: one term per enabled language."""

    translations = models.JSONField(_("translations"), default=dict)
    note = models.TextField(_("note"), blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("glossary term")
        verbose_name_plural = _("glossary terms")
        ordering = ["id"]

    def __str__(self):
        return next((term for term in self.translations.values() if term), f"#{self.pk}")

    def term(self, code: str) -> str:
        return self.translations.get(code, "")


@receiver([post_save, post_delete], sender=Language)
def _invalidate_language_cache(**kwargs):
    from django.core.cache import cache

    cache.delete("lorebook:languages")
