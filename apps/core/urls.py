from django.urls import path

from .views.demo import demo

urlpatterns = [
    path("", demo, name="demo"),
]
