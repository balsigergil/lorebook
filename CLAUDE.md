# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Lorebook is a self-hostable documentation platform (a GitBook alternative): a Django 6 monolith
(ASGI, Python 3.14) shipped as one Docker image. `README.md` is the user-facing overview;
`PLAN.md` (in French) is the design document and explains the reasoning behind the architecture.

## Commands

Development needs PostgreSQL. `docker compose -f compose.dev.yaml up -d` starts PostgreSQL and
Mailpit; settings come from `.env` (see `.env.example`).

```bash
uv sync && npm install
uv run manage.py migrate
uv run manage.py seed_demo --admin-password demo   # sample content
npm run dev                                         # Vite dev server (used when DJANGO_DEBUG is on)
uv run manage.py runserver
uv run manage.py db_worker                          # task worker, or set LOREBOOK_TASKS_IMMEDIATE=true
```

Tests (pytest-django, run against PostgreSQL with `--reuse-db`; tasks run immediately under test):

```bash
uv run pytest                                   # whole suite
uv run pytest tests/test_publishing.py          # one file
uv run pytest tests/test_search.py -k accent    # one test by name
uv run pytest --create-db                       # after changing migrations
```

Everything the CI checks:

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest
uv run manage.py makemigrations --check
uv run manage.py generate_api_client --check
npm run typecheck && npm run build
```

`scripts/format.sh <file>` fixes imports and formats one file. Ruff's line length is 100.

## Architecture

**Three interfaces, one instance.** The public portal (`/`), internal portal (`/internal`) and
editing interface (`/edit`) are wired in `lorebook/urls.py`; `apps/portal/urls.py` is mounted
twice, under the `public` and `internal` namespaces, and the same views behave differently per
portal. An administrator can give each interface its own domain: `PortalHostMiddleware`
(`apps/core/middleware.py`) then swaps `request.urlconf` for `lorebook/urls_<interface>.py`.
Routes in `lorebook/urls_shared.py` (accounts, API, files, comments) exist on every domain.
Because an interface may live on another domain, build cross-interface links with
`portal_reverse()` / `portal_home()` from `apps/core/portals.py`, not plain `reverse()`.

**Layers.** Apps live in `apps/`, split by domain (table in `README.md`). Business logic goes in
each app's `services.py` and uses the ORM directly; views stay thin. Ports/adapters are reserved
for external boundaries: search (`apps/search/backends/`, chosen by `LOREBOOK_SEARCH_BACKEND`)
and media storage (local or S3 via django-storages).

**Permissions** live in `apps/access/services.py`. Groups get a reader/editor/admin role per
collection; articles can restrict reading to groups, inherited by sub-articles. Reader-facing
queries (portal pages, search, sitemap) must be filtered through these helpers
(`readable_collections`, `readable_article_ids`, `can_read_article`…), which take the current
portal. Media files are always served through Django after a permission check.

**Content model.** Articles form a tree inside a collection; each has one translation per
language with a draft, published version and revisions (`apps/content/services.py`: `save_draft`,
`publish`, `restore_revision`, `move_article`). Content is stored as Tiptap/ProseMirror JSON; HTML
is rendered by `apps/content/rendering.py` at publication and stored. Bump `RENDERER_VERSION`
whenever the rendered output changes so stored HTML is re-rendered on next read. Markdown import
and export are in `apps/content/markdown.py`.

**Frontend.** Pages are server-rendered Django templates with htmx, Alpine and the Bloum
component library (CSS classes and shadow-DOM-free custom elements; docs at
https://www.bloum.dev/llms.txt). Only the text editor is React (Tiptap, `assets/editor/`), built
by Vite and included through the `vite` template tag (`apps/core/templatetags/vite.py`), which
uses the dev server or the build manifest. Tailwind 4 is available via Vite.

**Internal API.** The editor talks to a Django Ninja API (`lorebook/api.py`, routers in each app's
`api.py`) through `assets/editor/api/client.ts`, generated from the OpenAPI schema. After changing
an API schema or endpoint, run `uv run manage.py generate_api_client` and commit the result.

**Forms.** Every form inherits `LoreForm` or `LoreModelForm` (`apps/core/forms/base_forms.py`).
Rendering goes through Django's form renderer with Bloum templates (`apps/core/templates/core/forms/`),
so never hand-write form HTML in pages. Forms post with htmx (`core/forms/htmx_form.html`); on a
validation error the view returns only the form fragment via `apps.core.views.form_invalid`.

**Background tasks** use Django's Tasks API with the PostgreSQL backend (`django-tasks-db`); task
functions are in each app's `tasks.py`. There is no Redis.

## Translations

The UI is written in English and translated into French, German and Italian (`locale/`). Wrap
new strings for gettext. The React editor gets its strings from Django (`editor_strings()` in
`apps/editor/views/articles.py`), so add editor strings there rather than in TypeScript. The
compiled `.mo` files are committed; after editing `.po` files:

```bash
uv run manage.py makemessages -l fr -l de -l it --ignore=.venv --ignore=node_modules \
  --ignore=dist --ignore=static --ignore=tests --no-location
uv run manage.py compilemessages --ignore=.venv
```
