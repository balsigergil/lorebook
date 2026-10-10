from django.test import RequestFactory

from apps.analytics import services as analytics
from apps.analytics.models import DailySalt, DailyViews, ViewFingerprint

BROWSER = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"


def request(ip="10.0.0.1", agent=BROWSER, **headers):
    return RequestFactory().get("/", REMOTE_ADDR=ip, HTTP_USER_AGENT=agent, **headers)


def test_counts_once_per_reader_and_day(published):
    article = published.article
    assert analytics.record_view(request(), article, "fr", "public")
    assert not analytics.record_view(request(), article, "fr", "public")
    assert analytics.record_view(request(ip="10.0.0.2"), article, "fr", "public")
    assert analytics.record_view(request(), article, "fr", "internal")
    views = DailyViews.objects.get(article=article, language="fr", portal="public")
    assert views.views == 2
    assert analytics.views_for(article) == 3


def test_bots_and_prefetch_are_ignored(published):
    article = published.article
    assert not analytics.record_view(request(agent="Googlebot/2.1"), article, "fr", "public")
    assert not analytics.record_view(request(agent=""), article, "fr", "public")
    assert not analytics.record_view(request(HTTP_SEC_PURPOSE="prefetch"), article, "fr", "public")
    assert not DailyViews.objects.exists()


def test_no_personal_data_is_stored(published):
    analytics.record_view(request(ip="203.0.113.7"), published.article, "fr", "public")
    fingerprint = ViewFingerprint.objects.get()
    assert "203.0.113.7" not in fingerprint.digest
    assert len(fingerprint.digest) == 64


def test_salt_rotates_and_old_data_is_forgotten(published):
    from datetime import timedelta

    from django.utils import timezone

    yesterday = timezone.localdate() - timedelta(days=1)
    DailySalt.objects.create(date=yesterday, salt="old")
    ViewFingerprint.objects.create(digest="x" * 64, date=yesterday)
    analytics.record_view(request(), published.article, "fr", "public")
    assert not DailySalt.objects.filter(date=yesterday).exists()
    assert not ViewFingerprint.objects.filter(date=yesterday).exists()


def test_most_read(published, public_collection):
    from apps.content import services as content

    other = content.create_article(public_collection, title="Autre", language="fr").article
    for index in range(3):
        analytics.record_view(request(ip=f"10.0.1.{index}"), other, "fr", "public")
    analytics.record_view(request(), published.article, "fr", "public")
    ranking = analytics.most_read({published.article_id, other.pk})
    assert ranking == [(other.pk, 3), (published.article_id, 1)]
    assert analytics.most_read({published.article_id}) == [(published.article_id, 1)]
