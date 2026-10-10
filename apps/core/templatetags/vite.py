import json
import logging
import re
from functools import cache

from django import template
from django.conf import settings
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.utils.html import format_html, format_html_join

register = template.Library()
logger = logging.getLogger(__name__)

PROD_PREFIX = "lorebook/"
MANIFEST_NAME = "lorebook/manifest.json"


@cache
def load_manifest() -> dict:
    path = finders.find(MANIFEST_NAME) or (settings.STATIC_ROOT / MANIFEST_NAME)
    try:
        with open(path) as fp:
            return json.load(fp)
    except OSError:
        logger.warning("Vite manifest not found; run `npm run build`.")
        return {}


def vite_manifest(entries_names):
    if settings.VITE_DEV_SERVER:
        scripts = [f"{settings.VITE_DEV_SERVER_URL}/@vite/client"]
        scripts += [f"{settings.VITE_DEV_SERVER_URL}/{name}" for name in entries_names]
        return scripts, []

    manifest = load_manifest()
    processed = set()

    def process(names):
        scripts, styles = [], []
        for name in names:
            if name in processed or name not in manifest:
                continue
            processed.add(name)
            chunk = manifest[name]
            import_scripts, import_styles = process(chunk.get("imports", []))
            scripts += import_scripts
            styles += import_styles
            if chunk.get("isEntry"):
                scripts.append(PROD_PREFIX + chunk["file"])
            styles += [PROD_PREFIX + css for css in chunk.get("css", [])]
        return scripts, styles

    return process(entries_names)


def to_url(path: str) -> str:
    return path if re.match("^https?://", path) else static(path)


@register.simple_tag(name="vite")
def vite_scripts_styles(*entries_names):
    scripts, styles = vite_manifest(entries_names)
    links = format_html_join(
        "\n", '<link rel="stylesheet" href="{}">', ((to_url(h),) for h in styles)
    )
    tags = format_html_join(
        "\n", '<script type="module" src="{}"></script>', ((to_url(s),) for s in scripts)
    )
    return format_html("{}\n{}", links, tags)
