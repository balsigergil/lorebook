# Lorebook

Lorebook is an open-source, self-hostable documentation platform, an alternative to GitBook
built with Django. One instance serves both the internal knowledge base and the public
documentation.

- **WYSIWYG editing** (Tiptap), autosaved drafts, publication, history and restore.
- **Multilingual**: write in any enabled language, translate by hand; publishing a version marks
  the others as outdated (unless the change is minor), and readers get a clear banner.
- **Three interfaces** in one instance: public portal, internal portal, editing interface, on one
  domain (`/`, `/internal`, `/edit`) or each on its own domain.
- **Permissions**: groups get a reader, editor or admin role per collection; articles can restrict
  reading to some groups, inherited by their sub-articles.
- **Full-text search** with PostgreSQL (one configuration per language, accent folding, typo
  tolerance), always filtered by the reader's rights.
- Editorial comments (never shown to readers), cookie-less read statistics, Markdown import and
  export, a shared glossary.
- Local accounts by invitation and generic OpenID Connect (Google Workspace, Microsoft Entra,
  Keycloak…).

Licensed under the [GNU AGPL v3](LICENSE).

## Run it with Docker

```bash
cp .env.example .env        # set DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS, the email server…
docker compose up -d        # web (ASGI), worker and PostgreSQL
docker compose exec web python manage.py createsuperuser
```

Open http://localhost:8000/edit/ and sign in. To try it with sample content instead:

```bash
docker compose exec web python manage.py seed_demo --admin-password <password>
```

The image runs `web` (Granian, ASGI, migrations applied at start) or `worker` (background tasks
from the PostgreSQL queue). Uploaded files live in the `uploads` volume, or in any S3-compatible
bucket with `LOREBOOK_MEDIA_STORAGE=s3`. Every setting is an environment variable, documented in
[`.env.example`](.env.example).

### Domains

By default the public portal is served at `/`, the internal portal at `/internal` and the editor
at `/edit`. In **Settings**, an administrator can give each interface its own domain (for example
`docs.example.com`, `kb.example.com`, `edit.example.com`), plus the main domain that keeps serving
the interfaces without one. Set `DJANGO_SESSION_COOKIE_DOMAIN=.example.com` so that a single
sign-in works on every domain.

## Development

Requirements: Python 3.14 with [uv](https://docs.astral.sh/uv/), Node 22, PostgreSQL 16+.

```bash
docker compose -f compose.dev.yaml up -d   # PostgreSQL and Mailpit, or use your own
cp .env.example .env
uv sync
npm install
uv run manage.py migrate
uv run manage.py seed_demo --admin-password demo   # optional
npm run dev                                         # Vite dev server
uv run manage.py runserver
uv run manage.py db_worker                          # background tasks (or LOREBOOK_TASKS_IMMEDIATE=true)
```

Checks run by the CI:

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest
uv run manage.py makemigrations --check
uv run manage.py generate_api_client --check
npm run typecheck && npm run build
```

### Translations

The interface is written in English and translated into French, German and Italian
(`locale/`). The compiled `.mo` files are committed, so building the image needs no gettext.

```bash
uv run manage.py makemessages -l fr -l de -l it --ignore=.venv --ignore=node_modules \
  --ignore=dist --ignore=static --ignore=tests --no-location
# translate the new entries in locale/*/LC_MESSAGES/django.po, then
uv run manage.py compilemessages --ignore=.venv
```

The interface follows the browser's language in the editor, and the content language on the
portals. The React editor gets its strings from Django (`editor_strings()` in
`apps/editor/views/articles.py`).

### Architecture

A Django monolith (ASGI) rendering every page on the server with Django templates, htmx and the
[Bloum](https://www.bloum.dev) component library. Only the text editor is a React island
(Tiptap), built with Vite and mounted in a server-rendered page. PostgreSQL holds everything:
content, full-text index and the task queue (Django's Tasks API).

| App                  | Domain                                                                         |
| -------------------- | ------------------------------------------------------------------------------ |
| `apps/core`          | Site settings, domain routing, `LoreForm` / `LoreModelForm`, shared templates   |
| `apps/content`       | Collections, article tree, translations, publication, revisions, renderer, Markdown |
| `apps/i18n`          | Content languages and glossary                                                  |
| `apps/access`        | Users, roles per collection, read restrictions, invitations, allauth adapters  |
| `apps/search`        | Full-text search port and its PostgreSQL adapter                                |
| `apps/media`         | Uploaded files, served after a permission check                                 |
| `apps/comments`      | Comment threads on articles                                                     |
| `apps/analytics`     | Cookie-less read counters, most read articles                                   |
| `apps/portal`        | Public and internal reader portals                                              |
| `apps/editor`        | Editing interface and administration                                            |

Business logic lives in each app's `services.py`; views stay thin. The editor talks to the
internal Django Ninja API (`lorebook/api.py`) through a TypeScript client generated from its
OpenAPI schema (`uv run manage.py generate_api_client`).

Every form inherits `LoreForm` or `LoreModelForm` (`apps/core/forms/base_forms.py`): widgets get
uniform Bloum attributes, rendering goes through Django's form renderer, and
`core/forms/htmx_form.html` posts with htmx; on a validation error the view answers with the
form fragment only (`apps.core.views.form_invalid`), which htmx swaps in place.

Articles are stored as Tiptap/ProseMirror JSON. The HTML is rendered by
`apps/content/rendering.py` at publication and stored; bump `RENDERER_VERSION` when the output
changes so it is re-rendered on the next read.
