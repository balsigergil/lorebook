from django.urls import path

from . import health

urlpatterns = [
    path("healthz", health.healthz, name="healthz"),
]
