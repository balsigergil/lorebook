from django.db.models import Count
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.access import services as access
from apps.analytics import services as analytics
from apps.content.models import Article, ArticleTranslation
from apps.i18n.services import default_language

from .common import editor_required, sidebar_context


@require_GET
@editor_required
def dashboard(request):
    collections = list(access.editable_collections(request.user))
    drafts = (
        ArticleTranslation.objects.filter(
            article__collection__in=collections, has_draft_changes=True
        )
        .select_related("article__collection", "draft_updated_by")
        .defer("draft_content", "content", "html", "text", "search_vector")
        .order_by("-draft_updated_at")[:10]
    )
    outdated = (
        ArticleTranslation.objects.filter(article__collection__in=collections, is_outdated=True)
        .select_related("article__collection")
        .defer("draft_content", "content", "html", "text", "search_vector")
        .order_by("-published_at")[:10]
    )
    article_ids = set(
        Article.objects.filter(collection__in=collections).values_list("id", flat=True)
    )
    top = analytics.most_read(article_ids, limit=5)
    titles = {
        translation.article_id: translation
        for translation in ArticleTranslation.objects.published()
        .filter(article_id__in=[pk for pk, _views in top])
        .select_related("article__collection")
        .defer("draft_content", "content", "html", "text", "search_vector")
    }
    popular = [(titles[pk], views) for pk, views in top if pk in titles]
    counts = dict(
        Article.objects.filter(collection__in=collections)
        .values_list("collection_id")
        .annotate(total=Count("id"))
        .values_list("collection_id", "total")
    )
    context = {
        **sidebar_context(request),
        "collections": [(collection, counts.get(collection.pk, 0)) for collection in collections],
        "drafts": drafts,
        "outdated": outdated,
        "popular": popular,
        "default_language": default_language(),
        "nav": "dashboard",
    }
    return render(request, "editor/dashboard.html", context)
