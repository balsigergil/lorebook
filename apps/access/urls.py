from django.urls import path

from . import views

app_name = "access"

urlpatterns = [
    path("invitation/<str:token>/", views.accept, name="accept-invitation"),
]
