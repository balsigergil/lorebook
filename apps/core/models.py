from django.core.cache import cache
from django.db import models
from django.utils.translation import gettext_lazy as _

CACHE_KEY = "lorebook:site-settings"


class SiteSettings(models.Model):
    """Instance-wide settings, edited in the administration. A single row."""

    site_name = models.CharField(_("site name"), max_length=100, default="Lorebook")
    tagline = models.CharField(_("tagline"), max_length=200, blank=True)
    main_host = models.CharField(
        _("main domain"),
        max_length=255,
        blank=True,
        help_text=_(
            "Domain serving the interfaces that have no dedicated domain, "
            "e.g. lorebook.example.com."
        ),
    )
    public_host = models.CharField(
        _("public portal domain"),
        max_length=255,
        blank=True,
        help_text=_("e.g. docs.example.com. Leave empty to serve the public portal at /."),
    )
    internal_host = models.CharField(
        _("internal portal domain"),
        max_length=255,
        blank=True,
        help_text=_("e.g. kb.example.com. Leave empty to serve the internal portal at /internal."),
    )
    edit_host = models.CharField(
        _("editing interface domain"),
        max_length=255,
        blank=True,
        help_text=_("e.g. edit.example.com. Leave empty to serve the editor at /edit."),
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("site settings")
        verbose_name_plural = _("site settings")

    def __str__(self):
        return self.site_name

    def save(self, *args, **kwargs):
        self.pk = 1
        for name in ("main_host", "public_host", "internal_host", "edit_host"):
            setattr(self, name, getattr(self, name).strip().lower())
        super().save(*args, **kwargs)
        cache.delete(CACHE_KEY)

    @classmethod
    def load(cls) -> SiteSettings:
        settings = cache.get(CACHE_KEY)
        if settings is None:
            settings = cls.objects.filter(pk=1).first() or cls(pk=1)
            cache.set(CACHE_KEY, settings, 30)
        return settings

    def host_for(self, portal: str) -> str:
        return {
            "public": self.public_host,
            "internal": self.internal_host,
            "edit": self.edit_host,
        }.get(portal, "")

    def portal_for_host(self, host: str) -> str | None:
        for portal in ("public", "internal", "edit"):
            if host and self.host_for(portal) == host:
                return portal
        return None
