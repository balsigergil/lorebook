from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.access import services as access
from apps.content.models import ArticleTranslation

from . import services
from .forms import CommentForm, ReplyForm
from .models import Comment, Thread


def readable_translation(request, translation_id: int) -> ArticleTranslation:
    translation = get_object_or_404(
        ArticleTranslation.objects.select_related("article__collection"), pk=translation_id
    )
    if not services.can_comment(request.user, translation):
        raise Http404
    return translation


def render_panel(request, translation, *, form=None, reply_forms=None, status=200):
    threads = list(services.threads_for(translation))
    reply_forms = reply_forms or {}
    for thread in threads:
        thread.reply_form = reply_forms.get(thread.pk) or ReplyForm(
            prefix=f"reply-{thread.pk}", auto_id=f"id_reply_{thread.pk}_%s"
        )
        thread.can_resolve = services.can_resolve(request.user, thread)
        for comment in thread.comments.all():
            comment.can_delete = services.can_delete(
                request.user, comment, translation.article.collection
            )
    context = {
        "translation": translation,
        "threads": threads,
        "open_count": sum(1 for thread in threads if not thread.is_resolved),
        "form": form or CommentForm(),
    }
    return render(request, "comments/panel.html", context, status=status)


@require_http_methods(["GET", "POST"])
def panel(request, translation_id):
    if not access.is_authenticated(request.user):
        return HttpResponseForbidden()
    translation = readable_translation(request, translation_id)
    if request.method == "POST":
        form = CommentForm(request.POST)
        if not form.is_valid():
            return render_panel(request, translation, form=form, status=422)
        services.start_thread(translation, request.user, form.cleaned_data["body"])
    return render_panel(request, translation)


@require_POST
def reply(request, thread_id):
    if not access.is_authenticated(request.user):
        return HttpResponseForbidden()
    thread = get_object_or_404(Thread, pk=thread_id)
    translation = readable_translation(request, thread.translation_id)
    form = ReplyForm(request.POST, prefix=f"reply-{thread.pk}", auto_id=f"id_reply_{thread.pk}_%s")
    if not form.is_valid():
        return render_panel(request, translation, reply_forms={thread.pk: form}, status=422)
    services.reply(thread, request.user, form.cleaned_data["body"])
    return render_panel(request, translation)


@require_POST
def resolve(request, thread_id):
    if not access.is_authenticated(request.user):
        return HttpResponseForbidden()
    thread = get_object_or_404(Thread.objects.select_related("translation__article"), pk=thread_id)
    translation = readable_translation(request, thread.translation_id)
    if not services.can_resolve(request.user, thread):
        return HttpResponseForbidden()
    services.set_resolved(thread, request.user, request.POST.get("resolved") == "1")
    return render_panel(request, translation)


@require_POST
def delete(request, comment_id):
    if not access.is_authenticated(request.user):
        return HttpResponseForbidden()
    comment = get_object_or_404(Comment.objects.select_related("thread"), pk=comment_id)
    translation = readable_translation(request, comment.thread.translation_id)
    if not services.can_delete(request.user, comment, translation.article.collection):
        return HttpResponseForbidden()
    services.delete_comment(comment)
    return render_panel(request, translation)
