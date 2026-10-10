from django.urls import path

from . import views

app_name = "comments"

urlpatterns = [
    path("<int:translation_id>/", views.panel, name="panel"),
    path("thread/<int:thread_id>/reply/", views.reply, name="reply"),
    path("thread/<int:thread_id>/resolve/", views.resolve, name="resolve"),
    path("<int:comment_id>/delete/", views.delete, name="delete"),
]
