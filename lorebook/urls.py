"""Default routing: the three interfaces share one domain under path prefixes.

An interface with its own domain is served by lorebook.urls_<interface>
instead (see apps.core.middleware.PortalHostMiddleware).
"""

from django.urls import include, path

from .urls_shared import urlpatterns as shared

urlpatterns = [
    *shared,
    path("internal/", include("apps.portal.urls", namespace="internal")),
    path("edit/", include("apps.editor.urls", namespace="edit")),
    path("", include("apps.portal.urls", namespace="public")),
]
