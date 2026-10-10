"""Routes served on every domain, whatever interface it hosts."""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from .api import api

urlpatterns = [
    path("", include("apps.core.urls")),
    path("accounts/", include("apps.access.urls")),
    path("accounts/", include("allauth.urls")),
    path("api/", api.urls),
    path("files/", include("apps.media.urls")),
    path("comments/", include("apps.comments.urls")),
    path("django-admin/", admin.site.urls),
]

if settings.DEBUG:
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    urlpatterns += staticfiles_urlpatterns()
