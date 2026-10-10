"""The sidebar of the editor: search across collections and the current language."""

from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import Resolver404, resolve, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from apps.access import services as access
from apps.content import services as content
from apps.core.views import is_htmx
from apps.i18n import services as i18n

from .common import editor_required, search_form, sidebar_context

# Pages showing one language of an article: switching language opens the
# article in the new language.
ARTICLE_LANGUAGE_VIEWS = {"edit:editor", "edit:history", "edit:revision"}


@require_GET
@editor_required
def search(request):
    """Articles of every editable collection whose title matches the query."""
    form = search_form(request.GET or None, auto_id="id_%s")
    form.fields["q"].widget.attrs.update(
        {"autofocus": True, "hx-target": "#search-results", "hx-push-url": "true"}
    )
    query = form.cleaned_data["q"].strip() if form.is_valid() else ""
    language = i18n.current_language(request.user)
    collections = access.editable_collections(request.user)
    results = content.search_titles(query, collections, language)
    context = {"query": query, "results": results, "current_language": language}
    if is_htmx(request):
        return render(request, "editor/search.html#results", context)
    return render(
        request,
        "editor/search.html",
        {**sidebar_context(request), **context, "form": form, "nav": "search"},
    )


@require_POST
@editor_required
def set_language(request):
    code = request.POST.get("language", "")
    if not i18n.is_enabled(code):
        raise Http404
    i18n.set_current_language(request.user, code)
    next_url = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect("edit:dashboard")
    try:
        match = resolve(next_url.split("?")[0], urlconf=getattr(request, "urlconf", None))
    except Resolver404:
        return redirect(next_url)
    if match.view_name in ARTICLE_LANGUAGE_VIEWS:
        return redirect(reverse("edit:editor", args=[match.kwargs["pk"], code]))
    return redirect(next_url)
