from django.core.exceptions import DisallowedHost

from .models import SiteSettings
from .portals import HOST_URLCONFS


class PortalHostMiddleware:
    """Serve an interface on its own domain when the administrator assigned one."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.portal_host = None
        try:
            host = request.get_host().rsplit(":", 1)[0].lower()
        except DisallowedHost:
            host = ""
        portal = SiteSettings.load().portal_for_host(host) if host else None
        if portal:
            request.portal_host = portal
            request.urlconf = HOST_URLCONFS[portal]
        return self.get_response(request)
