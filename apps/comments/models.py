from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Thread(models.Model):
    """A discussion attached to a language version of an article."""

    translation = models.ForeignKey(
        "content.ArticleTranslation", on_delete=models.CASCADE, related_name="threads"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name = _("thread")
        verbose_name_plural = _("threads")
        ordering = ["resolved_at", "-created_at"]

    def __str__(self):
        return f"Thread #{self.pk}"

    @property
    def is_resolved(self) -> bool:
        return self.resolved_at is not None


class Comment(models.Model):
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    body = models.TextField(_("comment"), max_length=5000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("comment")
        verbose_name_plural = _("comments")
        ordering = ["created_at"]

    def __str__(self):
        return self.body[:50]
