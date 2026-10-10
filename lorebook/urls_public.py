from django.urls import include, path

from .urls_shared import urlpatterns as shared

urlpatterns = [*shared, path("", include("apps.portal.urls", namespace="public"))]
