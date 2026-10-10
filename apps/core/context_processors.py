from django.utils.functional import SimpleLazyObject

from apps.access import services as access
from apps.i18n.services import default_language, enabled_languages

from .models import SiteSettings
from .portals import EDIT, INTERNAL, PUBLIC, portal_home


def lorebook(request):
    return {
        "site_settings": SimpleLazyObject(SiteSettings.load),
        "content_languages": SimpleLazyObject(enabled_languages),
        "default_content_language": SimpleLazyObject(default_language),
        "portal_links": SimpleLazyObject(
            lambda: {
                PUBLIC: portal_home(PUBLIC, request),
                INTERNAL: portal_home(INTERNAL, request),
                EDIT: portal_home(EDIT, request),
            }
        ),
        "user_can_edit": SimpleLazyObject(lambda: access.is_editor_somewhere(request.user)),
        "user_is_admin": SimpleLazyObject(lambda: access.is_instance_admin(request.user)),
    }
