from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.utils.translation import get_language_info

from apps.analytics.models import DailyViews
from apps.content.models import Article, ArticleTranslation

from .models import KNOWN_LANGUAGES, GlossaryTerm, Language

CACHE_KEY = "lorebook:languages"


def enabled_languages() -> list[Language]:
    languages = cache.get(CACHE_KEY)
    if languages is None:
        languages = list(Language.objects.enabled())
        cache.set(CACHE_KEY, languages, 30)
    return languages


def enabled_codes() -> list[str]:
    return [language.code for language in enabled_languages()]


def default_language() -> str:
    codes = enabled_codes()
    return codes[0] if codes else "en"


def is_enabled(code: str) -> bool:
    return code in enabled_codes()


def language_name(code: str) -> str:
    for language in enabled_languages():
        if language.code == code:
            return language.name
    if code in KNOWN_LANGUAGES:
        return KNOWN_LANGUAGES[code][0]
    try:
        return get_language_info(code)["name_local"]
    except KeyError:
        return code


def current_language(user) -> str:
    """The content language a user writes in, chosen in the editor's sidebar."""
    code = getattr(user, "content_language", "")
    return code if is_enabled(code) else default_language()


def set_current_language(user, code: str) -> None:
    if is_enabled(code) and user.content_language != code:
        user.content_language = code
        user.save(update_fields=["content_language"])


def search_config(code: str) -> str:
    return KNOWN_LANGUAGES.get(code, ("", "lorebook_simple"))[1]


def negotiate(accept_language: str) -> str:
    """Pick the enabled content language that best matches an Accept-Language header."""
    codes = enabled_codes()
    if not codes:
        return "en"
    weighted = []
    for index, part in enumerate(accept_language.split(",")):
        piece = part.strip()
        if not piece:
            continue
        lang, _sep, params = piece.partition(";")
        quality = 1.0
        if params.strip().startswith("q="):
            try:
                quality = float(params.strip()[2:])
            except ValueError:
                quality = 0.0
        weighted.append((-quality, index, lang.strip().lower().split("-")[0]))
    for _quality, _index, lang in sorted(weighted):
        if lang in codes:
            return lang
    return codes[0]


def invalidate_cache() -> None:
    cache.delete(CACHE_KEY)


@transaction.atomic
def delete_language(language: Language) -> None:
    """Delete a language and everything written in it.

    Its article translations go, with their revisions and comments. An article
    left without any translation goes too, unless a sub-article still has one.
    """
    code = language.code
    translations = ArticleTranslation.objects.filter(language=code)
    article_ids = set(translations.values_list("article_id", flat=True))
    translations.delete()
    while True:
        # Leaves first: deleting an article deletes its sub-articles.
        orphans = list(
            Article.objects.filter(
                pk__in=article_ids, translations__isnull=True, children__isnull=True
            ).values_list("pk", flat=True)
        )
        if not orphans:
            break
        Article.objects.filter(pk__in=orphans).delete()
    for term in GlossaryTerm.objects.filter(translations__has_key=code):
        term.translations.pop(code)
        if any(term.translations.values()):
            term.save(update_fields=["translations", "updated_at"])
        else:
            term.delete()
    DailyViews.objects.filter(language=code).delete()
    get_user_model().objects.filter(content_language=code).update(content_language="")
    language.delete()
