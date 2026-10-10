from django.urls import path, register_converter

from . import seo, views
from .converters import LanguageConverter

register_converter(LanguageConverter, "lang")

app_name = "portal"

urlpatterns = [
    path("", views.root, name="home"),
    path("sitemap.xml", seo.sitemap, name="sitemap"),
    path("robots.txt", seo.robots, name="robots"),
    path("<lang:lang>/", views.home, name="home-lang"),
    path("<lang:lang>/search/", views.search, name="search"),
    path("<lang:lang>/<slug:collection>/", views.collection, name="collection"),
    path("<lang:lang>/<slug:collection>/<slug:article>/", views.article, name="article"),
]
