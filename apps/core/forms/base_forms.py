from django import forms
from django.forms import (
    CheckboxInput,
    CheckboxSelectMultiple,
    ClearableFileInput,
    FileInput,
    RadioSelect,
    Select,
    SelectMultiple,
    Textarea,
)
from django.forms.renderers import TemplatesSetting
from django.utils.translation import gettext_lazy as _


class LoreFormRenderer(TemplatesSetting):
    """Renders every Django form with Bloum components (Form Field, Input, Switch…)."""

    form_template_name = "core/forms/form.html"
    field_template_name = "core/forms/field.html"


def widget_css_class(widget) -> str:
    if isinstance(widget, CheckboxInput):
        return "switch"
    if isinstance(widget, (RadioSelect, CheckboxSelectMultiple)):
        return "input-check"
    if isinstance(widget, (Select, SelectMultiple)):
        return "input input-combobox"
    return "input"


def style_widget(field: forms.Field) -> None:
    widget = field.widget
    classes = widget.attrs.get("class", "").split()
    for css in widget_css_class(widget).split():
        if css not in classes:
            classes.append(css)
    widget.attrs["class"] = " ".join(classes)

    if isinstance(widget, CheckboxInput):
        widget.attrs.setdefault("role", "switch")
    if isinstance(widget, Textarea):
        widget.attrs.setdefault("rows", 4)
        widget.attrs.setdefault("data-autogrow", "")
    if isinstance(widget, (FileInput, ClearableFileInput)):
        widget.attrs["class"] = "input"

    if isinstance(field, forms.DateTimeField):
        if not isinstance(widget, forms.DateTimeInput):
            field.widget = widget = forms.DateTimeInput(attrs=widget.attrs)
        widget.input_type = "datetime-local"
        widget.format = widget.format or "%Y-%m-%dT%H:%M"
        field.localize = False
    elif isinstance(field, forms.DateField):
        if not isinstance(widget, forms.DateInput):
            field.widget = widget = forms.DateInput(attrs=widget.attrs)
        widget.input_type = "date"
        widget.format = widget.format or "%Y-%m-%d"
        field.localize = False


class LoreFormMixin:
    """Behaviour shared by every Lorebook form.

    - Widgets get uniform Bloum attributes (input, switch, combobox…).
    - Rendering goes through LoreFormRenderer: no hand-written form HTML.
    - `core/forms/htmx_form.html` wraps the form in a <form> posting with
      htmx; when validation fails, the view sends back only that fragment
      (see apps.core.views.form_invalid) and htmx swaps it in place.

    Options a view can set on an instance before rendering:
    `action` (URL posted to), `submit_label`, `cancel_url`, `form_id`,
    `danger` (destructive submit button).
    """

    template_name_div = "core/forms/form.html"
    required_css_class = "required"
    submit_label = _("Save")
    action = ""
    cancel_url = ""
    danger = False
    form_id = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.form_id:
            prefix = f"{self.prefix}-" if self.prefix else ""
            self.form_id = f"form-{prefix}{self.__class__.__name__.lower()}"
        for field in self.fields.values():
            style_widget(field)


class LoreForm(LoreFormMixin, forms.Form):
    pass


class LoreModelForm(LoreFormMixin, forms.ModelForm):
    pass
