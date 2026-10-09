import json
import re

from django import template
from django.conf import settings
from django.templatetags.static import static
from django.utils.safestring import mark_safe

register = template.Library()

DEV_SERVER_ROOT = "http://localhost:5173/static/lorebook"
PROD_PREFIX = "lorebook/"
MANIFEST_PATH = "static/lorebook/manifest.json"


def vite_manifest(entries_names):
    if settings.DEBUG:
        scripts = [
            f"{DEV_SERVER_ROOT}/@vite/client",
        ]

        for name in entries_names:
            scripts.append(f"{DEV_SERVER_ROOT}/{name}")

        styles = []
        return scripts, styles
    else:
        with open(MANIFEST_PATH) as fp:
            manifest = json.load(fp)
        _processed = set()

        def _process_entries(names):
            scripts = []
            styles = []

            for name in names:
                if name in _processed:
                    continue

                chunk = manifest[name]

                import_scripts, import_styles = _process_entries(
                    chunk.get("imports", [])
                )
                scripts += import_scripts
                styles += import_styles

                scripts += [PROD_PREFIX + chunk["file"]]
                styles += [PROD_PREFIX + css for css in chunk.get("css", [])]

                _processed.add(name)

            return scripts, styles

        return _process_entries(entries_names)


def is_absolute_url(url):
    return re.match("^https?://", url)


def as_link_tag(href):
    return f'<link rel="stylesheet" href="{href}" />'


def as_script_tag(src):
    return f'<script type="module" src="{src}"></script>'


@register.simple_tag(name="vite")
def vite_scripts_styles(*entries_names):
    scripts, styles = vite_manifest(entries_names)
    styles = map(lambda href: href if is_absolute_url(href) else static(href), styles)
    scripts = map(lambda src: src if is_absolute_url(src) else static(src), scripts)

    result = [
        *map(as_link_tag, styles),
        *map(as_script_tag, scripts),
    ]

    return mark_safe("\n".join(result))  # noqa: S308
