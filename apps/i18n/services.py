from django.core.cache import cache
from django.utils.translation import get_language_info

from .models import KNOWN_LANGUAGES, Language

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
