"""Media files: upload and access control.

The storage itself is the port: Django's default storage, configured as the
local disk or any S3-compatible bucket (django-storages) in settings.STORAGES.
"""

import mimetypes
import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.utils.text import get_valid_filename
from django.utils.translation import gettext as _

from apps.access import services as access
from apps.content.models import Collection

from .models import MediaFile

ALLOWED_TYPES = {
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "image/avif",
    "application/pdf",
}


def store_upload(collection: Collection, upload: UploadedFile, user=None) -> MediaFile:
    content_type = upload.content_type or mimetypes.guess_type(upload.name or "")[0] or ""
    if content_type not in ALLOWED_TYPES:
        raise ValidationError(_("This file type is not allowed."))
    if upload.size > settings.MEDIA_MAX_UPLOAD_SIZE:
        raise ValidationError(_("This file is too large."))
    name = get_valid_filename(os.path.basename(upload.name or "file")) or "file"
    media = MediaFile(
        collection=collection,
        original_name=upload.name or name,
        content_type=content_type,
        size=upload.size,
        uploaded_by=user,
    )
    media.file.save(name, upload, save=False)
    media.save()
    return media


def can_read_media(user, media: MediaFile) -> bool:
    collection = media.collection
    if collection.is_public:
        return True
    return access.can_read_collection(user, collection, access.INTERNAL)
