import os

from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
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
