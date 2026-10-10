from html import escape

from django.db import connection

from apps.content.models import ArticleTranslation
from apps.i18n.models import KNOWN_LANGUAGES

from .base import SearchHit

START, STOP = "⁣[", "]⁣"


def config_case(column: str) -> str:
    """SQL expression mapping a language code column to its search configuration."""
    whens = " ".join(
        f"WHEN '{code}' THEN '{config}'::regconfig"
        for code, (_n, config) in KNOWN_LANGUAGES.items()
    )
    return f"(CASE {column} {whens} ELSE 'lorebook_simple'::regconfig END)"


def highlight(snippet: str) -> str:
    """Escape a ts_headline snippet, keeping only our own highlight markers."""
    return escape(snippet).replace(escape(START), "<mark>").replace(escape(STOP), "</mark>")


class PostgresSearchBackend:
    """PostgreSQL full-text search, one configuration per language, with
    trigram similarity on titles to tolerate typos."""

    TITLE_SIMILARITY = 0.35

    def index(self, translation) -> None:
        with connection.cursor() as cursor:
            # The SQL is built from constants only (language configurations).
            cursor.execute(
                f"""
                UPDATE content_articletranslation
                SET search_vector =
                    setweight(to_tsvector({config_case("language")}, coalesce(title, '')), 'A')
                    || setweight(to_tsvector({config_case("language")}, coalesce(text, '')), 'B')
                WHERE id = %s
                """,  # noqa: S608
                [translation.pk],
            )

    def remove(self, translation) -> None:
        ArticleTranslation.objects.filter(pk=translation.pk).update(search_vector=None)

    def search(
        self, query: str, *, language: str, article_ids: set[int], limit: int = 20
    ) -> list[SearchHit]:
        query = query.strip()
        if not query or not article_ids:
            return []
        config = config_case("t.language")
        # The SQL is built from constants only; the query is a parameter.
        sql = f"""
            SELECT t.id, t.article_id, t.language, t.title,
                   ts_headline({config}, t.text, q,
                       'MaxFragments=2, MaxWords=24, MinWords=8, FragmentDelimiter=" … ", '
                       || 'StartSel="{START}", StopSel="{STOP}"') AS snippet,
                   ts_rank_cd(t.search_vector, q) + word_similarity(%s, t.title) AS rank
            FROM content_articletranslation t,
                 LATERAL websearch_to_tsquery({config}, %s) q
            WHERE t.published_at IS NOT NULL
              AND t.article_id = ANY(%s)
              AND (t.search_vector @@ q OR word_similarity(%s, t.title) > %s)
            ORDER BY (t.language = %s) DESC, rank DESC
            LIMIT %s
        """  # noqa: S608
        with connection.cursor() as cursor:
            cursor.execute(
                sql,
                [
                    query,
                    query,
                    list(article_ids),
                    query,
                    self.TITLE_SIMILARITY,
                    language,
                    limit * 4,
                ],
            )
            rows = cursor.fetchall()

        # One hit per article, preferring the reader's language.
        hits: dict[int, SearchHit] = {}
        for translation_id, article_id, lang, title, snippet, rank in rows:
            if article_id in hits:
                continue
            hits[article_id] = SearchHit(
                translation_id=translation_id,
                article_id=article_id,
                language=lang,
                title=title,
                snippet=highlight(snippet or ""),
                rank=float(rank or 0),
            )
        return sorted(hits.values(), key=lambda hit: (hit.language != language, -hit.rank))[:limit]
