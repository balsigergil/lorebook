from django.db import transaction
from django.utils import timezone

from apps.access import services as access
from apps.content.models import ArticleTranslation, Collection

from .models import Comment, Thread


def can_comment(user, translation: ArticleTranslation) -> bool:
    """Comments belong to the writing process: only the editors of the collection see them."""
    return access.can_edit_collection(user, translation.article.collection)


def can_resolve(user, thread: Thread) -> bool:
    if not access.is_authenticated(user):
        return False
    return thread.author_id == user.pk or access.can_edit_collection(
        user, thread.translation.article.collection
    )


def can_delete(user, comment: Comment, collection: Collection) -> bool:
    """The author of a comment, or an administrator of its collection, can delete it."""
    if not access.is_authenticated(user):
        return False
    return comment.author_id == user.pk or access.can_admin_collection(user, collection)


@transaction.atomic
def start_thread(translation: ArticleTranslation, user, body: str) -> Thread:
    thread = Thread.objects.create(translation=translation, author=user)
    Comment.objects.create(thread=thread, author=user, body=body)
    return thread


def reply(thread: Thread, user, body: str) -> Comment:
    return Comment.objects.create(thread=thread, author=user, body=body)


@transaction.atomic
def delete_comment(comment: Comment) -> None:
    """Delete a comment, and its thread when no comment is left in it."""
    thread = comment.thread
    comment.delete()
    if not thread.comments.exists():
        thread.delete()


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
