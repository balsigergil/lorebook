import os

from django import template
from django.utils.html import format_html_join

from apps.core.forms.base_forms import widget_css_class
from apps.core.portals import portal_reverse

register = template.Library()


@register.filter
def get_item(dictionary, key):
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter
def get_attr(obj, attr):
    return getattr(obj, attr, None)


@register.filter
def addstr(arg1, arg2):
    """concatenate arg1 & arg2"""
    return str(arg1) + str(arg2)


@register.filter
def basename(path) -> str:
    """Last component of a path, e.g. a file's name without its upload directory"""
    return os.path.basename(str(path))


@register.simple_tag
def lore_widget(bound_field):
    """Render a field's widget, adding the Bloum classes forms not built on LoreForm lack."""
    widget = bound_field.field.widget
    attrs = {}
    if "class" not in widget.attrs:
        attrs["class"] = widget_css_class(widget)
    if bound_field.errors:
        attrs["aria-invalid"] = "true"
    return bound_field.as_widget(attrs=attrs)


@register.simple_tag(takes_context=True)
def portal_url(context, portal, viewname, *args, **kwargs):
    """URL of a view of another interface (public, internal, edit), possibly on another domain."""
    return portal_reverse(
        portal, viewname, args=args or None, kwargs=kwargs or None, request=context.get("request")
    )


@register.simple_tag
def html_attrs(attrs: dict):
    return format_html_join(" ", '{}="{}"', attrs.items())
