"""Search engine files of the public portal: sitemap.xml and robots.txt."""

from django.contrib.auth.models import AnonymousUser
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET

from apps.access import services as access
from apps.content.models import ArticleTranslation
from apps.core.models import SiteSettings
from apps.core.portals import EDIT, INTERNAL, PUBLIC
from apps.i18n.services import enabled_codes

from .views import current_portal


@require_GET
@cache_page(60 * 15)
def sitemap(request):
    """Every public, published article, with its language versions as alternates."""
    if current_portal(request) != PUBLIC:
        raise Http404
    readable = access.readable_article_ids_everywhere(AnonymousUser(), access.PUBLIC)
    codes = set(enabled_codes())
    translations = (
        ArticleTranslation.objects.published()
        .filter(article_id__in=readable, language__in=codes)
        .select_related("article__collection")
        .only(
            "language",
            "published_at",
            "article__slug",
            "article__collection__slug",
        )
        .order_by("article_id", "language")
    )
    by_article: dict[int, list] = {}
    for translation in translations:
        by_article.setdefault(translation.article_id, []).append(translation)

    def absolute(translation):
        path = reverse(
            "portal:article",
            kwargs={
                "lang": translation.language,
                "collection": translation.article.collection.slug,
                "article": translation.article.slug,
            },
            current_app=PUBLIC,
        )
        return request.build_absolute_uri(path)

    entries = []
    for versions in by_article.values():
        alternates = [(version.language, absolute(version)) for version in versions]
        for version in versions:
            entries.append(
                {
                    "loc": absolute(version),
                    "lastmod": version.published_at,
                    "alternates": alternates,
                }
            )
    return render(
        request, "portal/sitemap.xml", {"entries": entries}, content_type="application/xml"
    )


@require_GET
def robots(request):
    portal = current_portal(request)
    lines = ["User-agent: *"]
    if portal == INTERNAL:
        lines.append("Disallow: /")
    else:
        site = SiteSettings.load()
        if not request.portal_host:
            # The other interfaces share this domain under their prefixes.
            if not site.host_for(INTERNAL):
                lines.append("Disallow: /internal/")
            if not site.host_for(EDIT):
                lines.append("Disallow: /edit/")
        lines += [
            "Disallow: /accounts/",
            "Disallow: /api/",
            "Disallow: /comments/",
            "Disallow: /django-admin/",
            "Disallow: /*/search/",
            "",
            "Sitemap: " + request.build_absolute_uri(reverse("portal:sitemap", current_app=PUBLIC)),
        ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")
