from django.http import HttpResponse
from django.shortcuts import redirect, render


def is_htmx(request) -> bool:
    return request.headers.get("HX-Request") == "true"


def form_invalid(request, form, *, template: str | None = None, context: dict | None = None):
    """Answer an invalid form.

    With htmx, only the form fragment is sent back (status 422) and swapped
    in place of the submitted form. Without htmx, `template` is rendered as a
    full page.
    """
    context = {"form": form, **(context or {})}
    if is_htmx(request) or template is None:
        return render(request, "core/forms/htmx_form.html", context, status=422)
    return render(request, template, context, status=422)


def htmx_redirect(request, url: str):
    """Redirect after a successful submission, whether it came from htmx or not."""
    if is_htmx(request):
        response = HttpResponse(status=200)
        response["HX-Redirect"] = url
        return response
    return redirect(url)


def htmx_refresh(request, fallback_url: str):
    if is_htmx(request):
        response = HttpResponse(status=200)
        response["HX-Refresh"] = "true"
        return response
    return redirect(fallback_url)
