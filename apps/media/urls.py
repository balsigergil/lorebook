from django.urls import path

from . import views

app_name = "media"

urlpatterns = [
    path("<uuid:pk>/<str:filename>", views.serve, name="file"),
]
