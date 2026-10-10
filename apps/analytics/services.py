"""Cookie-less read statistics.

A view is counted server side, at most once per reader, article, language,
portal and day. Readers are told apart by a SHA-256 hash of their IP address
and user agent salted with a random value that rotates every day; past
salts and hashes are deleted, so no data outlives the day.
"""

import hashlib
import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, connection, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.content.models import Article

from .models import DailySalt, DailyViews, ViewFingerprint

BOT_RE = re.compile(
    r"bot|crawl|spider|slurp|archiver|facebookexternalhit|embedly|preview|monitor|"
    r"curl|wget|python-requests|httpx|aiohttp|go-http-client|java/|headless|lighthouse|"
    r"pingdom|uptime",
    re.IGNORECASE,
)


def is_bot(user_agent: str) -> bool:
    return not user_agent or bool(BOT_RE.search(user_agent))


def client_ip(request) -> str:
    if getattr(settings, "USE_X_FORWARDED_HOST", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def todays_salt(today) -> str:
    salt = DailySalt.objects.filter(date=today).values_list("salt", flat=True).first()
    if salt:
        return salt
    try:
        with transaction.atomic():
            DailySalt.objects.create(date=today, salt=secrets.token_hex(32))
    except IntegrityError:
        pass
    # A new day: forget yesterday's salt and hashes.
    DailySalt.objects.filter(date__lt=today).delete()
    ViewFingerprint.objects.filter(date__lt=today).delete()
    return DailySalt.objects.get(date=today).salt


def record_view(request, article: Article, language: str, portal: str) -> bool:
    """Count a read. Returns False when the request is ignored (bot, prefetch, duplicate)."""
    user_agent = request.META.get("HTTP_USER_AGENT", "")
    if is_bot(user_agent):
        return False
    purpose = request.META.get("HTTP_SEC_PURPOSE", "") or request.META.get("HTTP_PURPOSE", "")
    if "prefetch" in purpose.lower():
        return False
    today = timezone.localdate()
    salt = todays_salt(today)
    raw = "|".join([salt, client_ip(request), user_agent, str(article.pk), language, portal])
    digest = hashlib.sha256(raw.encode()).hexdigest()
    try:
        with transaction.atomic():
            ViewFingerprint.objects.create(digest=digest, date=today)
    except IntegrityError:
        return False
    with connection.cursor() as cursor:
        # Table name and placeholders only: no user input in the SQL text.
        cursor.execute(
            f"""
            INSERT INTO {DailyViews._meta.db_table} (article_id, language, portal, date, views)
            VALUES (%s, %s, %s, %s, 1)
            ON CONFLICT (article_id, language, portal, date)
            DO UPDATE SET views = {DailyViews._meta.db_table}.views + 1
            """,  # noqa: S608
            [article.pk, language, portal, today],
        )
    return True


def most_read(article_ids: set[int], days: int = 30, limit: int = 5) -> list[tuple[int, int]]:
    """(article id, views) of the most read articles among article_ids."""
    if not article_ids:
        return []
    since = timezone.localdate() - timedelta(days=days)
    rows = (
        DailyViews.objects.filter(article_id__in=article_ids, date__gte=since)
        .values("article_id")
        .annotate(total=Sum("views"))
        .order_by("-total")[:limit]
    )
    return [(row["article_id"], row["total"]) for row in rows]


def views_for(article: Article, days: int = 30) -> int:
    since = timezone.localdate() - timedelta(days=days)
    return (
        DailyViews.objects.filter(article=article, date__gte=since).aggregate(total=Sum("views"))[
            "total"
        ]
        or 0
    )
