from django.db import transaction
from django.utils import timezone

from apps.access import services as access
from apps.content.models import ArticleTranslation

from .models import Comment, Thread


def can_comment(user, translation: ArticleTranslation) -> bool:
    """Comments are internal: any signed-in user who can read the article."""
    return access.is_authenticated(user) and access.can_read_article(
        user, translation.article, access.INTERNAL
    )


def can_resolve(user, thread: Thread) -> bool:
    if not access.is_authenticated(user):
        return False
    return thread.author_id == user.pk or access.can_edit_collection(
        user, thread.translation.article.collection
    )


@transaction.atomic
def start_thread(translation: ArticleTranslation, user, body: str) -> Thread:
    thread = Thread.objects.create(translation=translation, author=user)
    Comment.objects.create(thread=thread, author=user, body=body)
    return thread


def reply(thread: Thread, user, body: str) -> Comment:
    return Comment.objects.create(thread=thread, author=user, body=body)


def set_resolved(thread: Thread, user, resolved: bool) -> None:
    thread.resolved_at = timezone.now() if resolved else None
    thread.resolved_by = user if resolved else None
    thread.save(update_fields=["resolved_at", "resolved_by"])


def threads_for(translation: ArticleTranslation):
    return (
        Thread.objects.filter(translation=translation)
        .select_related("author", "resolved_by")
        .prefetch_related("comments__author")
    )
