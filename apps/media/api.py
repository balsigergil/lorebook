from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.urls import reverse
from ninja import File, Router, Schema
from ninja.errors import HttpError
from ninja.files import UploadedFile

from apps.access import services as access
from apps.content.models import Collection

from .services import store_upload

router = Router(tags=["media"])


class MediaOut(Schema):
    id: str
    url: str
    name: str
    content_type: str
    size: int


@router.post("/collections/{collection_id}/media", response={201: MediaOut})
def upload(request, collection_id: int, file: File[UploadedFile]):
    collection = get_object_or_404(Collection, pk=collection_id)
    if not access.can_edit_collection(request.user, collection):
        raise HttpError(403, "You cannot upload files to this collection.")
    try:
        media = store_upload(collection, file, request.user)
    except ValidationError as error:
        raise HttpError(422, " ".join(error.messages)) from error
    url = reverse("media:file", kwargs={"pk": media.pk, "filename": media.filename})
    return 201, MediaOut(
        id=str(media.pk),
        url=url,
        name=media.original_name,
        content_type=media.content_type,
        size=media.size,
    )
