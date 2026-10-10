from datetime import datetime

from django.shortcuts import get_object_or_404
from ninja import Router, Schema
from ninja.errors import HttpError

from apps.access import services as access

from . import services
from .models import ArticleTranslation

router = Router(tags=["content"])


class TranslationOut(Schema):
    id: int
    article_id: int
    language: str
    title: str
    content: dict
    status: str
    is_outdated: bool
    has_draft_changes: bool
    draft_updated_at: datetime


class DraftIn(Schema):
    title: str
    content: dict


class DraftSaved(Schema):
    saved_at: datetime
    has_draft_changes: bool


def editable_translation(request, translation_id: int) -> ArticleTranslation:
    translation = get_object_or_404(
        ArticleTranslation.objects.select_related("article__collection"), pk=translation_id
    )
    if not access.can_edit_collection(request.user, translation.article.collection):
        raise HttpError(403, "You cannot edit this article.")
    return translation


@router.get("/translations/{translation_id}", response=TranslationOut)
def get_translation(request, translation_id: int):
    translation = editable_translation(request, translation_id)
    return TranslationOut(
        id=translation.pk,
        article_id=translation.article_id,
        language=translation.language,
        title=translation.draft_title,
        content=translation.draft_content,
        status=translation.status,
        is_outdated=translation.is_outdated,
        has_draft_changes=translation.has_draft_changes,
        draft_updated_at=translation.draft_updated_at,
    )


@router.put("/translations/{translation_id}/draft", response=DraftSaved)
def save_draft(request, translation_id: int, payload: DraftIn):
    translation = editable_translation(request, translation_id)
    if payload.content.get("type") != "doc":
        raise HttpError(422, "The content must be a Tiptap document.")
    services.save_draft(
        translation, title=payload.title, content=payload.content, user=request.user
    )
    return DraftSaved(saved_at=translation.draft_updated_at, has_draft_changes=True)
