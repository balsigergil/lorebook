from django import forms
from django.forms import CheckboxInput, RadioSelect, Select
from django.forms.renderers import TemplatesSetting


class LoreFormRenderer(TemplatesSetting):
    form_template_name = "core/forms/generic_form.html"


class LoreForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.update_form_fields()

    def update_form_fields(self):
        for _field_name, field in self.fields.items():
            if isinstance(field.widget, (CheckboxInput, RadioSelect)):
                field.widget.attrs.update({"class": "input-check"})
            elif isinstance(field.widget, Select):
                field.widget.attrs.update({"class": "input-combobox"})
            else:
                field.widget.attrs.update({"class": "input"})

            if isinstance(field, forms.DateField):
                if not isinstance(field.widget, forms.DateInput):
                    field.widget = forms.DateInput(attrs={"class": "input"})
                field.widget.input_type = "date"
                field.localize = False
                if not getattr(field.widget, "format", None):
                    field.widget.format = "%Y-%m-%d"
            if isinstance(field, forms.DateTimeField):
                if not isinstance(field.widget, forms.DateTimeInput):
                    field.widget = forms.DateTimeInput(attrs={"class": "input"})
                field.widget.input_type = "datetime-local"
                field.localize = False
                if not getattr(field.widget, "format", None):
                    field.widget.format = "%Y-%m-%dT%H:%M"


class LoreModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for _field_name, field in self.fields.items():
            if isinstance(field.widget, (CheckboxInput, RadioSelect)):
                field.widget.attrs.update({"class": "input-check"})
            elif isinstance(field.widget, Select):
                field.widget.attrs.update({"class": "input-combobox"})
            else:
                field.widget.attrs.update({"class": "input"})

            if isinstance(field, forms.DateField):
                if not isinstance(field.widget, forms.DateInput):
                    field.widget = forms.DateInput(attrs={"class": "input"})
                field.widget.input_type = "date"
                field.localize = False
                if not getattr(field.widget, "format", None):
                    field.widget.format = "%Y-%m-%d"
            if isinstance(field, forms.DateTimeField):
                if not isinstance(field.widget, forms.DateTimeInput):
                    field.widget = forms.DateTimeInput(attrs={"class": "input"})
                field.widget.input_type = "datetime-local"
                field.localize = False
                if not getattr(field.widget, "format", None):
                    field.widget.format = "%Y-%m-%dT%H:%M"
