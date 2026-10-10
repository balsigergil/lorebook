from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.translation import gettext as _

from apps.access import services as access
from apps.content.models import Article, Collection
from apps.core.forms import SearchForm
from apps.i18n import services as i18n


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


def search_form(data=None, *, auto_id: str) -> SearchForm:
    """The search of articles by title, across every editable collection."""
    form = SearchForm(data, placeholder=_("Search articles…"), auto_id=auto_id)
    form.fields["q"].widget.attrs.update(
        {
            "hx-get": reverse("edit:search"),
            "hx-trigger": "input changed delay:250ms, search",
            "hx-target": "#sidebar-search-results",
            "hx-swap": "innerHTML",
        }
    )
    return form


def sidebar_context(request) -> dict:
    language = i18n.current_language(request.user)
    return {
        "editable_collections": list(access.editable_collections(request.user)),
        "sidebar_search_form": search_form(auto_id="id_sidebar_%s"),
        "current_language": language,
        "current_language_name": i18n.language_name(language),
    }
