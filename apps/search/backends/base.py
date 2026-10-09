from dataclasses import dataclass
from typing import Protocol


@dataclass
class SearchHit:
    translation_id: int
    article_id: int
    language: str
    title: str
    snippet: str
    rank: float


class SearchBackend(Protocol):
    """Port for the full-text search engine."""

    def index(self, translation) -> None:
        """(Re)index a published translation."""

    def remove(self, translation) -> None:
        """Drop a translation from the index."""

    def search(
        self, query: str, *, language: str, article_ids: set[int], limit: int = 20
    ) -> list[SearchHit]:
        """Published translations matching the query, restricted to article_ids."""
