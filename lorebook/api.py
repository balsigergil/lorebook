"""Internal API used by the editor (Django Ninja, session authentication with CSRF).

The TypeScript client of the editor is generated from its OpenAPI schema:
`uv run manage.py generate_api_client`.
"""

from ninja import NinjaAPI
from ninja.security import django_auth

from apps.content.api import router as content_router
from apps.i18n.api import router as i18n_router
from apps.media.api import router as media_router

api = NinjaAPI(
    title="Lorebook internal API",
    version="1",
    auth=django_auth,
    urls_namespace="api",
)
api.add_router("/", content_router)
api.add_router("/", media_router)
api.add_router("/", i18n_router)
