from django.db import models
from django.utils.translation import gettext_lazy as _


class DailyViews(models.Model):
    """Read counter of an article, per language, portal and day. No personal data."""

    article = models.ForeignKey(
        "content.Article", on_delete=models.CASCADE, related_name="daily_views"
    )
    language = models.CharField(max_length=8)
    portal = models.CharField(max_length=16)
    date = models.DateField()
    views = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = _("daily views")
        verbose_name_plural = _("daily views")
        constraints = [
            models.UniqueConstraint(
                fields=["article", "language", "portal", "date"], name="unique_daily_views"
            )
        ]
        indexes = [models.Index(fields=["date"])]

    def __str__(self):
        return f"{self.article_id} {self.language} {self.portal} {self.date}: {self.views}"


class ViewFingerprint(models.Model):
    """Anonymised hash used to count a reader once per article and day.

    It is derived from a salt that rotates every day and is then forgotten,
    so it cannot be linked back to a person or across days.
    """

    digest = models.CharField(max_length=64, unique=True)
    date = models.DateField(db_index=True)

    def __str__(self):
        return self.digest


class DailySalt(models.Model):
    date = models.DateField(unique=True)
    salt = models.CharField(max_length=64)

    def __str__(self):
        return str(self.date)
