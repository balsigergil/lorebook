from django.urls import path

from .views import admin, articles, collections, dashboard

app_name = "edit"

urlpatterns = [
    path("", dashboard.dashboard, name="dashboard"),
    # Collections
    path("collections/new/", collections.collection_create, name="collection-create"),
    path("c/<slug:slug>/", collections.collection_detail, name="collection"),
    path("c/<slug:slug>/settings/", collections.collection_settings, name="collection-settings"),
    path("c/<slug:slug>/delete/", collections.collection_delete, name="collection-delete"),
    path(
        "c/<slug:slug>/permissions/",
        collections.collection_permissions,
        name="collection-permissions",
    ),
    path(
        "c/<slug:slug>/permissions/<int:pk>/delete/",
        collections.collection_role_delete,
        name="collection-role-delete",
    ),
    path("c/<slug:slug>/articles/new/", collections.article_create, name="article-create"),
    path("c/<slug:slug>/import/", collections.markdown_import, name="import"),
    path(
        "c/<slug:slug>/articles/<int:pk>/reorder/",
        collections.article_reorder,
        name="article-reorder",
    ),
    # Articles
    path("a/<int:pk>/", articles.article_redirect, name="article"),
    path("a/<int:pk>/settings/", articles.article_settings, name="article-settings"),
    path("a/<int:pk>/delete/", articles.article_delete, name="article-delete"),
    path("a/<int:pk>/<str:lang>/", articles.editor, name="editor"),
    path("a/<int:pk>/<str:lang>/create/", articles.translation_create, name="translation-create"),
    path("a/<int:pk>/<str:lang>/publish/", articles.publish, name="publish"),
    path("a/<int:pk>/<str:lang>/unpublish/", articles.unpublish, name="unpublish"),
    path("a/<int:pk>/<str:lang>/discard/", articles.discard_draft, name="discard"),
    path("a/<int:pk>/<str:lang>/history/", articles.history, name="history"),
    path("a/<int:pk>/<str:lang>/history/<int:number>/", articles.revision, name="revision"),
    path(
        "a/<int:pk>/<str:lang>/history/<int:number>/restore/",
        articles.revision_restore,
        name="revision-restore",
    ),
    path("a/<int:pk>/<str:lang>/export.md", articles.export_markdown, name="export"),
    # Glossary
    path("glossary/", admin.glossary, name="glossary"),
    path("glossary/new/", admin.glossary_create, name="glossary-create"),
    path("glossary/<int:pk>/", admin.glossary_edit, name="glossary-edit"),
    # Administration
    path("settings/", admin.site_settings, name="settings"),
    path("settings/languages/", admin.languages, name="languages"),
    path("settings/languages/<int:pk>/", admin.language_update, name="language-update"),
    path("settings/groups/", admin.groups, name="groups"),
    path("settings/groups/<int:pk>/", admin.group_detail, name="group"),
    path("settings/users/", admin.users, name="users"),
    path("settings/users/<int:pk>/", admin.user_detail, name="user"),
    path("settings/invitations/<int:pk>/", admin.invitation_action, name="invitation-action"),
    path("profile/", admin.profile, name="profile"),
]
