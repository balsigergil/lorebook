from django.core.files.storage import FileSystemStorage
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from .models import MediaFile
from .services import can_read_media


@require_GET
def serve(request, pk, filename):
    media = get_object_or_404(MediaFile.objects.select_related("collection"), pk=pk)
    if not can_read_media(request.user, media):
        raise Http404
    storage = media.file.storage
    if not isinstance(storage, FileSystemStorage):
        # Remote storage: hand out a short-lived signed URL.
        return HttpResponseRedirect(media.file.url)
    response = FileResponse(media.file.open("rb"), content_type=media.content_type)
    response["Content-Disposition"] = (
        "inline" if media.content_type.startswith("image/") else "attachment"
    ) + f'; filename="{media.filename}"'
    response["X-Content-Type-Options"] = "nosniff"
    visibility = "public" if media.collection.is_public else "private"
    response["Cache-Control"] = f"{visibility}, max-age=86400"
    return response
