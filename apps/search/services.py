from functools import cache

from django.conf import settings
from django.utils.module_loading import import_string

from .backends.base import SearchBackend, SearchHit


@cache
def get_backend() -> SearchBackend:
    return import_string(settings.LOREBOOK_SEARCH_BACKEND)()


def search(query: str, *, language: str, article_ids: set[int], limit: int = 20) -> list[SearchHit]:
    return get_backend().search(query, language=language, article_ids=article_ids, limit=limit)
