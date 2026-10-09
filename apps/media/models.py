import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


def upload_to(instance: MediaFile, filename: str) -> str:
    return f"media/{instance.pk.hex[:2]}/{instance.pk.hex}/{filename}"


class MediaFile(models.Model):
    """A file uploaded from the editor. It is readable by whoever can read its collection."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    collection = models.ForeignKey(
        "content.Collection", on_delete=models.CASCADE, related_name="media_files"
    )
    file = models.FileField(upload_to=upload_to, max_length=300)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size = models.PositiveBigIntegerField(default=0)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("media file")
        verbose_name_plural = _("media files")
        ordering = ["-created_at"]

    def __str__(self):
        return self.original_name

    @property
    def filename(self) -> str:
        return self.file.name.rsplit("/", 1)[-1]
