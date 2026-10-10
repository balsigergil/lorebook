from django import template
from django.urls import NoReverseMatch, reverse

register = template.Library()


@register.simple_tag(takes_context=True)
def switch_language(context, code: str) -> str:
    """The current page in another content language."""
    request = context["request"]
    match = request.resolver_match
    if match is None or "lang" not in match.kwargs:
        return reverse("portal:home-lang", kwargs={"lang": code}, current_app=request.portal)
    kwargs = {**match.kwargs, "lang": code}
    try:
        url = reverse(match.view_name, kwargs=kwargs, current_app=match.namespace)
    except NoReverseMatch:
        return reverse("portal:home-lang", kwargs={"lang": code}, current_app=match.namespace)
    query = request.GET.urlencode()
    return f"{url}?{query}" if query else url


@register.filter
def in_path(node, article) -> bool:
    """Whether the tree node is the current article or one of its ancestors."""
    if article is None:
        return False
    if node.article.pk == article.pk:
        return True
    return any(child_contains(child, article) for child in node.children)


def child_contains(node, article) -> bool:
    if node.article.pk == article.pk:
        return True
    return any(child_contains(child, article) for child in node.children)
