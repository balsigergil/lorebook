from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.access import services as access
from apps.access.models import CollectionRole
from apps.content import markdown
from apps.content import services as content
from apps.content.models import ArticleTranslation
from apps.core.views import form_invalid, htmx_redirect
from apps.i18n.services import default_language, enabled_languages

from ..forms import ArticleCreateForm, CollectionForm, CollectionRoleForm, MarkdownImportForm
from .common import admin_required, editor_required, get_collection, sidebar_context


@require_http_methods(["GET", "POST"])
@admin_required
def collection_create(request):
    form = CollectionForm(request.POST or None)
    form.submit_label = _("Create the collection")
    if request.method == "POST":
        if not form.is_valid():
            return form_invalid(request, form)
        collection = form.save()
        messages.success(request, _("Collection created."))
        return htmx_redirect(request, reverse("edit:collection", args=[collection.slug]))
    return render(
        request,
        "editor/form_page.html",
        {**sidebar_context(request), "form": form, "title": _("New collection")},
    )


def status_matrix(collection, tree_nodes):
    """For each article, its translation per enabled language."""
    languages = enabled_languages()
    translations: dict[int, dict[str, ArticleTranslation]] = {}
    for translation in ArticleTranslation.objects.filter(article__collection=collection).defer(
        "draft_content", "content", "html", "text", "search_vector"
    ):
        translations.setdefault(translation.article_id, {})[translation.language] = translation
    restricted = set(
        access.restrictions_for([node.article.pk for node in content.flatten(tree_nodes)])
    )
    rows = []

    def walk(nodes, depth):
        for node in nodes:
            per_language = translations.get(node.article.pk, {})
            rows.append(
                {
                    "node": node,
                    "depth": depth,
                    "cells": [
                        (language, per_language.get(language.code)) for language in languages
                    ],
                    "restricted": node.article.pk in restricted,
                }
            )
            walk(node.children, depth + 1)

    walk(tree_nodes, 0)
    return rows


@require_GET
@editor_required
def collection_detail(request, slug):
    collection = get_collection(request, slug)
    language = request.GET.get("lang") or default_language()
    articles = list(collection.articles.all())
    titles = content.translations_for_display(articles, language, published_only=False)
    tree = content.build_tree(articles, titles)
    create_form = ArticleCreateForm(collection=collection, language=language)
    create_form.action = reverse("edit:article-create", args=[collection.slug])
    import_form = MarkdownImportForm(collection=collection, initial={"language": language})
    import_form.action = reverse("edit:import", args=[collection.slug])
    context = {
        **sidebar_context(request),
        "collection": collection,
        "rows": status_matrix(collection, tree),
        "languages": enabled_languages(),
        "language": language,
        "create_form": create_form,
        "import_form": import_form,
        "can_admin": access.can_admin_collection(request.user, collection),
        "nav": f"collection-{collection.pk}",
    }
    return render(request, "editor/collection.html", context)


@require_http_methods(["GET", "POST"])
@editor_required
def collection_settings(request, slug):
    collection = get_collection(request, slug, admin=True)
    form = CollectionForm(request.POST or None, instance=collection)
    if request.method == "POST":
        if not form.is_valid():
            return form_invalid(request, form)
        collection = form.save()
        messages.success(request, _("Collection updated."))
        return htmx_redirect(request, reverse("edit:collection", args=[collection.slug]))
    return render(
        request,
        "editor/collection_settings.html",
        {
            **sidebar_context(request),
            "collection": collection,
            "form": form,
            "can_delete": access.is_instance_admin(request.user),
            "nav": f"collection-{collection.pk}",
        },
    )


@require_POST
@admin_required
def collection_delete(request, slug):
    collection = get_collection(request, slug, admin=True)
    if request.POST.get("confirm") != collection.slug:
        messages.error(request, _("Type the slug of the collection to confirm."))
        return redirect("edit:collection-settings", slug=collection.slug)
    collection.delete()
    messages.success(request, _("Collection deleted."))
    return htmx_redirect(request, reverse("edit:dashboard"))


@require_http_methods(["GET", "POST"])
@editor_required
def collection_permissions(request, slug):
    collection = get_collection(request, slug, admin=True)
    form = CollectionRoleForm(request.POST or None, collection=collection)
    form.action = reverse("edit:collection-permissions", args=[collection.slug])
    if request.method == "POST":
        if not form.is_valid():
            return form_invalid(request, form)
        form.save()
        messages.success(request, _("Role granted."))
        return htmx_redirect(request, form.action)
    roles = CollectionRole.objects.filter(collection=collection).select_related("group")
    return render(
        request,
        "editor/collection_permissions.html",
        {
            **sidebar_context(request),
            "collection": collection,
            "roles": roles,
            "form": form,
            "nav": f"collection-{collection.pk}",
        },
    )


@require_POST
@editor_required
def collection_role_delete(request, slug, pk):
    collection = get_collection(request, slug, admin=True)
    role = get_object_or_404(CollectionRole, pk=pk, collection=collection)
    role.delete()
    messages.success(request, _("Role removed."))
    return htmx_redirect(request, reverse("edit:collection-permissions", args=[collection.slug]))


@require_POST
@editor_required
def article_create(request, slug):
    collection = get_collection(request, slug)
    form = ArticleCreateForm(request.POST, collection=collection)
    form.action = reverse("edit:article-create", args=[collection.slug])
    if not form.is_valid():
        return form_invalid(request, form, context={"in_modal": True})
    translation = content.create_article(
        collection,
        title=form.cleaned_data["title"],
        language=form.cleaned_data["language"],
        parent=form.cleaned_data["parent"],
        user=request.user,
    )
    return htmx_redirect(
        request, reverse("edit:editor", args=[translation.article_id, translation.language])
    )


@require_POST
@editor_required
def markdown_import(request, slug):
    collection = get_collection(request, slug)
    form = MarkdownImportForm(request.POST, request.FILES, collection=collection)
    form.action = reverse("edit:import", args=[collection.slug])
    if not form.is_valid():
        return form_invalid(request, form, context={"in_modal": True})
    title, doc = markdown.markdown_to_doc(form.markdown)
    if not title:
        title = form.cleaned_data["file"].name.rsplit(".", 1)[0].replace("-", " ").capitalize()
    with transaction.atomic():
        translation = content.create_article(
            collection,
            title=title,
            language=form.cleaned_data["language"],
            parent=form.cleaned_data["parent"],
            content=doc,
            user=request.user,
        )
        if form.cleaned_data["publish"]:
            content.publish(translation, user=request.user, note=_("Imported from Markdown"))
    messages.success(request, _("Markdown imported."))
    return htmx_redirect(
        request, reverse("edit:editor", args=[translation.article_id, translation.language])
    )


@require_POST
@editor_required
def article_reorder(request, slug, pk):
    collection = get_collection(request, slug)
    article = get_object_or_404(collection.articles, pk=pk)
    siblings = list(
        collection.articles.filter(parent_id=article.parent_id).order_by("position", "id")
    )
    index = siblings.index(article)
    direction = request.POST.get("direction")
    if direction == "up" and index > 0:
        content.move_article(article, article.parent, index - 1)
    elif direction == "down" and index < len(siblings) - 1:
        content.move_article(article, article.parent, index + 1)
    elif direction not in ("up", "down"):
        raise PermissionDenied
    return htmx_redirect(request, reverse("edit:collection", args=[collection.slug]))
