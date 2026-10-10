"""The three interfaces of an instance and the URLs between them.

By default they share one domain, under path prefixes (/, /internal, /edit).
An administrator can give each one its own domain; PortalHostMiddleware then
serves that domain with a urlconf holding only that interface.
"""

from django.conf import settings
from django.urls import reverse

from .models import SiteSettings

PUBLIC = "public"
INTERNAL = "internal"
EDIT = "edit"

HOST_URLCONFS = {
    PUBLIC: "lorebook.urls_public",
    INTERNAL: "lorebook.urls_internal",
    EDIT: "lorebook.urls_edit",
}

HOME_VIEWS = {
    PUBLIC: "portal:home",
    INTERNAL: "portal:home",
    EDIT: "edit:dashboard",
}


def portal_reverse(portal: str, viewname: str, *, args=None, kwargs=None, request=None) -> str:
    """URL of a view of a given interface, absolute when it lives on another domain."""
    site = SiteSettings.load()
    host = site.host_for(portal)
    current_portal_host = getattr(request, "portal_host", None) if request else None
    if host:
        path = reverse(
            viewname, urlconf=HOST_URLCONFS[portal], args=args, kwargs=kwargs, current_app=portal
        )
        if request is not None and current_portal_host == portal:
            return path
        scheme = request.scheme if request is not None else settings.ACCOUNT_DEFAULT_HTTP_PROTOCOL
        return f"{scheme}://{host}{path}"
    path = reverse(
        viewname, urlconf=settings.ROOT_URLCONF, args=args, kwargs=kwargs, current_app=portal
    )
    if current_portal_host and site.main_host:
        return f"{request.scheme}://{site.main_host}{path}"
    return path


def portal_home(portal: str, request=None) -> str:
    return portal_reverse(portal, HOME_VIEWS[portal], request=request)
