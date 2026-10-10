import json

from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.access import services as access
from apps.comments.services import can_comment
from apps.content import markdown
from apps.content import services as content
from apps.content.models import ArticleTranslation, Revision
from apps.content.rendering import render_document
from apps.core.views import form_invalid, htmx_redirect
from apps.i18n import services as i18n
from apps.i18n.models import GlossaryTerm

from ..forms import ArticleSettingsForm, PublishForm, TranslationCreateForm
from .common import editor_required, get_article, sidebar_context


def article_context(request, article, language: str) -> dict:
    translations = {item.language: item for item in article.translations.all()}
    languages = [
        (language_obj, translations.get(language_obj.code))
        for language_obj in i18n.enabled_languages()
    ]
    ancestors = article.ancestors()
    ancestor_titles = content.translations_for_display(ancestors, language, published_only=False)
    return {
        **sidebar_context(request),
        "collection": article.collection,
        "article": article,
        "language": language,
        "language_name": i18n.language_name(language),
        "translations": translations,
        "languages": languages,
        "breadcrumbs": [(ancestor, ancestor_titles.get(ancestor.pk)) for ancestor in ancestors],
        "inherited_restrictions": access.inherited_restrictions(article),
        "nav": f"collection-{article.collection_id}",
    }


def editor_strings() -> dict[str, str]:
    """Interface strings of the React editor, translated by Django."""
    return {
        "saved": _("Saved"),
        "changed": _("Unpublished changes"),
        "pending": _("Editing…"),
        "saving": _("Saving…"),
        "error": _("Not saved — retrying"),
        "title": _("Title"),
        "titlePlaceholder": _("Untitled"),
        "placeholder": _("Write something, or type # for a heading, - for a list…"),
        "toolbar": _("Formatting"),
        "undo": _("Undo"),
        "redo": _("Redo"),
        "blockType": _("Block type"),
        "paragraph": _("Paragraph"),
        "heading2": _("Heading 1"),
        "heading3": _("Heading 2"),
        "heading4": _("Heading 3"),
        "bold": _("Bold"),
        "italic": _("Italic"),
        "underline": _("Underline"),
        "strike": _("Strikethrough"),
        "code": _("Inline code"),
        "link": _("Link"),
        "linkPrompt": _("Link address (leave empty to remove the link)"),
        "bulletList": _("Bulleted list"),
        "orderedList": _("Numbered list"),
        "taskList": _("Checklist"),
        "quote": _("Quote"),
        "codeBlock": _("Code block"),
        "image": _("Image"),
        "insert": _("Insert…"),
        "calloutInfo": _("Info callout"),
        "calloutSuccess": _("Success callout"),
        "calloutWarning": _("Warning callout"),
        "calloutDanger": _("Danger callout"),
        "table": _("Table"),
        "divider": _("Divider"),
        "addRow": _("Add a row"),
        "addColumn": _("Add a column"),
        "deleteRow": _("Delete the row"),
        "deleteColumn": _("Delete the column"),
        "deleteTable": _("Delete the table"),
        "uploadFailed": _("The upload failed"),
    }


@require_GET
@editor_required
def article_redirect(request, pk):
    article = get_article(request, pk)
    codes = i18n.enabled_codes()
    translation = (
        article.translations.filter(language=i18n.default_language()).first()
        or article.translations.filter(language__in=codes).first()
        or article.translations.first()
    )
    language = translation.language if translation else i18n.default_language()
    return redirect("edit:editor", pk=article.pk, lang=language)


@require_GET
@editor_required
def editor(request, pk, lang):
    article = get_article(request, pk)
    context = article_context(request, article, lang)
    translation = context["translations"].get(lang)
    if translation is None:
        if not i18n.is_enabled(lang):
            raise Http404
        sources = [
            (item, i18n.language_name(item.language)) for item in context["translations"].values()
        ]
        form = TranslationCreateForm(sources=sources)
        form.action = reverse("edit:translation-create", args=[article.pk, lang])
        return render(request, "editor/translation_create.html", {**context, "form": form})

    publish_form = PublishForm(outdated=translation.is_outdated)
    publish_form.action = reverse("edit:publish", args=[article.pk, lang])
    settings_form = ArticleSettingsForm(instance=article)
    settings_form.action = reverse("edit:article-settings", args=[article.pk])
    settings_form.form_id = "form-article-settings"
    glossary = [
        [term.translations.get(code, "") for code in i18n.enabled_codes()]
        for term in GlossaryTerm.objects.all()
    ]
    editor_props = {
        "translationId": translation.pk,
        "collectionId": article.collection_id,
        "language": lang,
        "title": translation.draft_title,
        "content": translation.draft_content,
        "draftUpdatedAt": translation.draft_updated_at.isoformat(),
        "hasDraftChanges": translation.has_draft_changes,
        "isPublished": translation.is_published,
        "apiBase": reverse("api:api-root"),
        "strings": editor_strings(),
    }
    context.update(
        {
            "translation": translation,
            "publish_form": publish_form,
            "settings_form": settings_form,
            "editor_props": editor_props,
            "glossary": glossary,
            "glossary_languages": i18n.enabled_languages(),
            "can_comment": can_comment(request.user, translation),
            "body_class": "editor-page",
        }
    )
    return render(request, "editor/editor.html", context)


@require_POST
@editor_required
def translation_create(request, pk, lang):
    article = get_article(request, pk)
    if not i18n.is_enabled(lang):
        raise Http404
    translations = {item.language: item for item in article.translations.all()}
    sources = [(item, i18n.language_name(item.language)) for item in translations.values()]
    form = TranslationCreateForm(request.POST, sources=sources)
    form.action = reverse("edit:translation-create", args=[article.pk, lang])
    if not form.is_valid():
        return form_invalid(request, form)
    source = translations.get(form.cleaned_data["source"])
    content.add_translation(article, lang, user=request.user, copy_from=source)
    return htmx_redirect(request, reverse("edit:editor", args=[article.pk, lang]))


def get_translation(request, pk, lang) -> ArticleTranslation:
    article = get_article(request, pk)
    return get_object_or_404(
        ArticleTranslation.objects.select_related("article"), article=article, language=lang
    )


@require_POST
@editor_required
def publish(request, pk, lang):
    translation = get_translation(request, pk, lang)
    form = PublishForm(request.POST, outdated=translation.is_outdated)
    form.action = reverse("edit:publish", args=[pk, lang])
    if not form.is_valid():
        return form_invalid(request, form, context={"in_modal": True})
    # The editor sends its current state along, so nothing typed since the
    # last autosave is lost.
    raw_content = request.POST.get("content")
    if raw_content:
        try:
            doc = json.loads(raw_content)
        except ValueError:
            doc = None
        if isinstance(doc, dict) and doc.get("type") == "doc":
            content.save_draft(
                translation,
                title=request.POST.get("title", translation.draft_title),
                content=doc,
                user=request.user,
            )
    content.publish(
        translation,
        user=request.user,
        kind=form.cleaned_data["kind"],
        note=form.cleaned_data["note"],
    )
    messages.success(request, _("Published."))
    return htmx_redirect(request, reverse("edit:editor", args=[pk, lang]))


@require_POST
@editor_required
def unpublish(request, pk, lang):
    translation = get_translation(request, pk, lang)
    content.unpublish(translation)
    messages.success(request, _("This version is no longer published."))
    return htmx_redirect(request, reverse("edit:editor", args=[pk, lang]))


@require_POST
@editor_required
def discard_draft(request, pk, lang):
    translation = get_translation(request, pk, lang)
    if translation.is_published:
        content.save_draft(
            translation, title=translation.title, content=translation.content, user=request.user
        )
        ArticleTranslation.objects.filter(pk=translation.pk).update(has_draft_changes=False)
        messages.success(request, _("Draft discarded."))
    return htmx_redirect(request, reverse("edit:editor", args=[pk, lang]))


@require_GET
@editor_required
def history(request, pk, lang):
    translation = get_translation(request, pk, lang)
    context = article_context(request, translation.article, lang)
    context.update(
        {
            "translation": translation,
            "revisions": translation.revisions.select_related("author").defer("content"),
        }
    )
    return render(request, "editor/history.html", context)


@require_GET
@editor_required
def revision(request, pk, lang, number):
    translation = get_translation(request, pk, lang)
    revision = get_object_or_404(Revision, translation=translation, number=number)
    context = article_context(request, translation.article, lang)
    context.update(
        {
            "translation": translation,
            "revision": revision,
            "rendered": render_document(revision.content),
        }
    )
    return render(request, "editor/revision.html", context)


@require_POST
@editor_required
def revision_restore(request, pk, lang, number):
    translation = get_translation(request, pk, lang)
    revision = get_object_or_404(Revision, translation=translation, number=number)
    content.restore_revision(revision, user=request.user)
    messages.success(
        request,
        _("Revision #%(number)s loaded into the draft. Publish it to make it live.")
        % {"number": revision.number},
    )
    return htmx_redirect(request, reverse("edit:editor", args=[pk, lang]))


@require_GET
@editor_required
def export_markdown(request, pk, lang):
    translation = get_translation(request, pk, lang)
    use_draft = request.GET.get("draft") == "1" or not translation.is_published
    title = translation.draft_title if use_draft else translation.title
    doc = translation.draft_content if use_draft else translation.content
    body = markdown.doc_to_markdown(doc, title=title)
    response = HttpResponse(body, content_type="text/markdown; charset=utf-8")
    filename = f"{slugify(title) or translation.article.slug}.{lang}.md"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@require_http_methods(["GET", "POST"])
@editor_required
def article_settings(request, pk):
    article = get_article(request, pk)
    form = ArticleSettingsForm(request.POST or None, instance=article)
    form.action = reverse("edit:article-settings", args=[article.pk])
    form.form_id = "form-article-settings"
    if request.method == "POST":
        if not form.is_valid():
            return form_invalid(
                request, form, context={"in_modal": True, "next_url": request.POST.get("next", "")}
            )
        form.save()
        messages.success(request, _("Article settings saved."))
        next_url = request.POST.get("next", "")
        if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            next_url = reverse("edit:article", args=[pk])
        return htmx_redirect(request, next_url)
    return redirect("edit:article", pk=pk)


@require_POST
@editor_required
def article_delete(request, pk):
    article = get_article(request, pk)
    collection = article.collection
    article.delete()
    messages.success(request, _("Article deleted, with its sub-articles."))
    return htmx_redirect(request, reverse("edit:collection", args=[collection.slug]))
