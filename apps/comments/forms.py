from django import forms
from django.utils.translation import gettext_lazy as _

from apps.core.forms import LoreForm


class CommentForm(LoreForm):
    submit_label = _("Comment")

    body = forms.CharField(
        label=_("Comment"),
        max_length=5000,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": _("Write a comment…")}),
    )


class ReplyForm(CommentForm):
    submit_label = _("Reply")
