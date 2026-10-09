from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from apps.access import services as access
from apps.content.models import Article, Collection


def editor_required(view):
    """Signed-in users holding the editor role on at least one collection."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not access.is_authenticated(request.user):
            return redirect_to_login(request.get_full_path())
        if not access.is_editor_somewhere(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


def admin_required(view):
    """Instance administrators only."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not access.is_authenticated(request.user):
            return redirect_to_login(request.get_full_path())
        if not access.is_instance_admin(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


def get_collection(request, slug: str, *, admin: bool = False) -> Collection:
    collection = get_object_or_404(Collection, slug=slug)
    allowed = (
        access.can_admin_collection(request.user, collection)
        if admin
        else access.can_edit_collection(request.user, collection)
    )
    if not allowed:
        raise PermissionDenied
    return collection


def get_article(request, pk: int) -> Article:
    article = get_object_or_404(Article.objects.select_related("collection"), pk=pk)
    if not access.can_edit_collection(request.user, article.collection):
        raise PermissionDenied
    return article


def sidebar_context(request) -> dict:
    return {"editable_collections": list(access.editable_collections(request.user))}
