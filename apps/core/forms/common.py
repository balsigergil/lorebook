from django import forms
from django.utils.translation import gettext_lazy as _

from .base_forms import LoreForm


class SearchForm(LoreForm):
    """A search box. The magnifier icon is set through the widget's data-icon attribute."""

    q = forms.CharField(
        label="",
        required=False,
        max_length=200,
        widget=forms.TextInput(
            attrs={"type": "search", "data-icon": "magnifying-glass", "autocomplete": "off"}
        ),
    )

    def __init__(self, *args, placeholder: str = "", size: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        widget = self.fields["q"].widget
        widget.attrs["placeholder"] = placeholder or _("Search…")
        widget.attrs["aria-label"] = _("Search")
        if size:
            widget.attrs["class"] += f" input-{size}"


class ConfirmForm(LoreForm):
    """Ask the user to type a value (e.g. a slug) before a destructive action."""

    danger = True
    submit_label = _("Delete")

    confirm = forms.CharField(label=_("Confirmation"), widget=forms.TextInput())

    def __init__(self, *args, expected: str, **kwargs):
        self.expected = expected
        super().__init__(*args, **kwargs)
        self.fields["confirm"].widget.attrs["autocomplete"] = "off"

    def clean_confirm(self):
        value = self.cleaned_data["confirm"].strip()
        if value != self.expected:
            raise forms.ValidationError(_("The value does not match."))
        return value
