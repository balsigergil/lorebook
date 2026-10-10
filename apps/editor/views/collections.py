from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.access import services as access
from apps.access.models import CollectionRole
from apps.content import markdown
from apps.content import services as content
from apps.content.models import ArticleTranslation
from apps.core.forms import ConfirmForm
from apps.core.views import form_invalid, htmx_redirect
from apps.i18n.services import current_language, enabled_languages, language_name

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
    language = current_language(request.user)
    articles = list(collection.articles.all())
    titles = content.translations_for_display(articles, language, published_only=False)
    tree = content.build_tree(articles, titles)
    import_form = MarkdownImportForm(collection=collection)
    import_form.action = reverse("edit:import", args=[collection.slug])
    context = {
        **sidebar_context(request),
        "collection": collection,
        "rows": status_matrix(collection, tree),
        "languages": enabled_languages(),
        "language": language,
        "language_name": language_name(language),
        "create_form": article_create_form(collection),
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
            "delete_form": delete_form(collection),
            "nav": f"collection-{collection.pk}",
        },
    )


def delete_form(collection, data=None) -> ConfirmForm:
    form = ConfirmForm(data, expected=collection.slug, prefix="delete")
    form.action = reverse("edit:collection-delete", args=[collection.slug])
    form.fields["confirm"].label = _("Type the slug of the collection to confirm")
    form.fields["confirm"].widget.attrs["placeholder"] = collection.slug
    return form


@require_POST
@admin_required
def collection_delete(request, slug):
    collection = get_collection(request, slug, admin=True)
    form = delete_form(collection, request.POST)
    if not form.is_valid():
        return form_invalid(request, form)
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


def article_create_form(collection, data=None, *, child=False, **kwargs) -> ArticleCreateForm:
    """The form of the "New article" modal, or of the "+" modal of a row (`child`).

    Both modals live on the same page: the second one gets its own ids.
    """
    action = reverse("edit:article-create", args=[collection.slug])
    if child:
        kwargs["auto_id"] = "id_child_%s"
        action += "?child=1"
    form = ArticleCreateForm(data, collection=collection, **kwargs)
    form.action = action
    if child:
        form.form_id = "form-child-article"
    return form


@require_http_methods(["GET", "POST"])
@editor_required
def article_create(request, slug):
    collection = get_collection(request, slug)
    language = current_language(request.user)
    if request.method == "GET":
        # The "+" of a row of the article table: the same modal, with the
        # parent article already selected, opened as soon as it is swapped in.
        parent_id = request.GET.get("parent", "")
        if not parent_id.isdigit():
            raise Http404
        parent = get_object_or_404(collection.articles, pk=parent_id)
        form = article_create_form(collection, initial={"parent": parent.pk}, child=True)
        return render(
            request,
            "editor/_article_create_modal.html",
            {
                "form": form,
                "modal_id": "modal-new-child-article",
                "language_name": language_name(language),
                "autoshow": True,
            },
        )
    form = article_create_form(collection, request.POST, child="child" in request.GET)
    if not form.is_valid():
        return form_invalid(request, form, context={"in_modal": True})
    translation = content.create_article(
        collection,
        title=form.cleaned_data["title"],
        language=language,
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
            language=current_language(request.user),
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
