"""Reader portals.

The same views serve the public portal (anonymous readers, public
collections) and the internal portal (signed-in readers); the portal is the
instance namespace the URL was resolved in.
"""

from functools import wraps

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import translation as ui_translation
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET

from apps.access import services as access
from apps.analytics import services as analytics
from apps.comments.services import can_comment
from apps.content import services as content
from apps.content.models import Article, ArticleTranslation, Collection
from apps.content.rendering import excerpt
from apps.core.forms import SearchForm
from apps.core.views import is_htmx
from apps.i18n import services as i18n
from apps.search import services as search_service


def current_portal(request) -> str:
    namespace = request.resolver_match.namespace if request.resolver_match else ""
    return access.INTERNAL if namespace == access.INTERNAL else access.PUBLIC


def reader_view(view):
    """Resolve the portal and the reader's language, and guard the internal portal.

    The interface switches to the content language when it is translated.
    """

    @wraps(view)
    def wrapper(request, *args, lang, **kwargs):
        portal = current_portal(request)
        if portal == access.INTERNAL and not access.is_authenticated(request.user):
            return redirect_to_login(request.get_full_path())
        if not i18n.is_enabled(lang):
            raise Http404
        request.portal = portal
        if lang in dict(settings.LANGUAGES):
            ui_translation.activate(lang)
            request.LANGUAGE_CODE = lang
        return view(request, *args, lang=lang, **kwargs)

    return wrapper


def portal_context(request, lang: str, collection: Collection | None = None) -> dict:
    portal = request.portal
    return {
        "search_form": SearchForm(request.GET or None, auto_id="header_%s"),
        "portal": portal,
        "is_internal": portal == access.INTERNAL,
        "lang": lang,
        "lang_name": i18n.language_name(lang),
        "collections": list(access.readable_collections(request.user, portal)),
        "current_collection": collection,
    }


def collection_navigation(request, collection: Collection, lang: str):
    """Readable, published articles of the collection, nested."""
    articles = list(collection.articles.all())
    readable = access.readable_article_ids(request.user, collection, request.portal, articles)
    titles = content.translations_for_display(
        [article for article in articles if article.pk in readable], lang, published_only=True
    )
    tree = content.build_tree(
        articles,
        titles,
        include=lambda article: article.pk in readable and titles.get(article.pk) is not None,
    )
    return tree


@require_GET
def root(request):
    portal = current_portal(request)
    if portal == access.INTERNAL and not access.is_authenticated(request.user):
        return redirect_to_login(request.get_full_path())
    lang = i18n.negotiate(request.headers.get("Accept-Language", ""))
    return redirect(reverse("portal:home-lang", kwargs={"lang": lang}, current_app=portal))


@require_GET
@reader_view
def home(request, lang):
    context = portal_context(request, lang)
    readable_ids = set()
    collection_cards = []
    for collection in context["collections"]:
        ids = access.readable_article_ids(request.user, collection, request.portal)
        readable_ids |= ids
        collection_cards.append(collection)

    popular = []
    top = analytics.most_read(readable_ids, limit=6)
    if top:
        articles = {
            article.pk: article
            for article in Article.objects.filter(pk__in=[pk for pk, _views in top]).select_related(
                "collection"
            )
        }
        titles = content.translations_for_display(list(articles.values()), lang, True)
        for article_id, views in top:
            article = articles.get(article_id)
            translation = titles.get(article_id)
            if article and translation:
                popular.append({"article": article, "translation": translation, "views": views})

    hero_search = SearchForm(
        auto_id="hero_%s", placeholder=_("Search the documentation…"), size="lg"
    )
    context.update(
        {"collection_cards": collection_cards, "popular": popular, "hero_search": hero_search}
    )
    return render(request, "portal/home.html", context)


def get_collection(request, slug: str) -> Collection:
    collection = get_object_or_404(Collection, slug=slug)
    if not access.can_read_collection(request.user, collection, request.portal):
        raise Http404
    return collection


@require_GET
@reader_view
def collection(request, lang, collection):
    collection = get_collection(request, collection)
    tree = collection_navigation(request, collection, lang)
    context = portal_context(request, lang, collection)
    context.update(
        {
            "tree": tree,
            "roots": [
                {"node": node, "excerpt": excerpt(node.translation.text or "", 160)}
                for node in tree
            ],
            "can_edit": request.portal == access.INTERNAL
            and access.can_edit_collection(request.user, collection),
        }
    )
    return render(request, "portal/collection.html", context)


@require_GET
@reader_view
def article(request, lang, collection, article):
    collection = get_collection(request, collection)
    article = get_object_or_404(Article, collection=collection, slug=article)
    if not access.can_read_article(request.user, article, request.portal):
        raise Http404
    translations = list(ArticleTranslation.objects.filter(article=article))
    version = content.pick_published(translations, lang)
    if version is None:
        raise Http404
    content.ensure_rendered(version.translation)
    analytics.record_view(request, article, version.translation.language, request.portal)

    tree = collection_navigation(request, collection, lang)
    flat = content.flatten(tree)
    index = next((i for i, node in enumerate(flat) if node.article.pk == article.pk), None)
    previous_node = flat[index - 1] if index not in (None, 0) else None
    next_node = flat[index + 1] if index is not None and index + 1 < len(flat) else None

    published_languages = {item.language for item in translations if item.is_published}
    ancestors = article.ancestors()
    ancestor_titles = content.translations_for_display(ancestors, lang, True)

    context = portal_context(request, lang, collection)
    context.update(
        {
            "tree": tree,
            "article": article,
            "translation": version.translation,
            "situation": version.situation,
            "up_to_date": version.up_to_date,
            "content_lang_name": i18n.language_name(version.translation.language),
            "available_languages": published_languages,
            "breadcrumbs": [
                (ancestor, ancestor_titles.get(ancestor.pk))
                for ancestor in ancestors
                if ancestor_titles.get(ancestor.pk) is not None
            ],
            "previous_node": previous_node,
            "next_node": next_node,
            "can_edit": request.portal == access.INTERNAL
            and access.can_edit_collection(request.user, collection),
            "can_comment": request.portal == access.INTERNAL
            and can_comment(request.user, version.translation),
        }
    )
    return render(request, "portal/article.html", context)


@require_GET
@reader_view
def search(request, lang):
    form = SearchForm(request.GET or None, placeholder=_("Search the documentation…"), size="lg")
    query = form.cleaned_data["q"].strip() if form.is_valid() else ""
    search_url = reverse("portal:search", kwargs={"lang": lang}, current_app=request.portal)
    form.fields["q"].widget.attrs.update(
        {
            "autofocus": True,
            "hx-get": search_url,
            "hx-trigger": "input changed delay:300ms, search",
            "hx-target": "#search-results",
            "hx-swap": "outerHTML",
            "hx-push-url": "true",
        }
    )
    context = portal_context(request, lang)
    results = []
    if query:
        readable = access.readable_article_ids_everywhere(request.user, request.portal)
        hits = search_service.search(query, language=lang, article_ids=readable, limit=30)
        articles = Article.objects.select_related("collection").in_bulk(
            [hit.article_id for hit in hits]
        )
        for hit in hits:
            article = articles.get(hit.article_id)
            if article is not None:
                results.append({"hit": hit, "article": article})
    context.update({"query": query, "results": results, "form": form})
    if is_htmx(request) and request.headers.get("HX-Request-Type") == "partial":
        return render(request, "portal/search.html#results", context)
    return render(request, "portal/search.html", context)
