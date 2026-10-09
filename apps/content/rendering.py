"""Render Tiptap/ProseMirror JSON documents to HTML and plain text.

The JSON document is the source of truth. The published HTML is rendered once
per publication and stored on the translation; bump RENDERER_VERSION whenever
the output changes so stored HTML is re-rendered on the next read.
"""

from dataclasses import dataclass, field
from html import escape
from urllib.parse import urlparse

from django.utils.text import slugify

RENDERER_VERSION = 1

SAFE_URL_SCHEMES = {"http", "https", "mailto", "tel", ""}
CALLOUT_VARIANTS = {"info", "success", "warning", "danger"}
CALLOUT_ICONS = {
    "info": "fa-circle-info",
    "success": "fa-circle-check",
    "warning": "fa-triangle-exclamation",
    "danger": "fa-circle-exclamation",
}
TOC_LEVELS = (2, 3)


@dataclass
class RenderResult:
    html: str
    toc: list[dict] = field(default_factory=list)
    text: str = ""


def safe_url(url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip()
    if url.startswith(("/", "#", "?")):
        return url
    try:
        scheme = urlparse(url).scheme.lower()
    except ValueError:
        return None
    if scheme not in SAFE_URL_SCHEMES:
        return None
    return url


def attr(value) -> str:
    return escape(str(value), quote=True)


class Renderer:
    def __init__(self):
        self.toc: list[dict] = []
        self.used_ids: set[str] = set()

    def render(self, doc: dict | None) -> RenderResult:
        if not doc or not isinstance(doc, dict):
            return RenderResult(html="")
        html = self.children(doc)
        return RenderResult(html=html, toc=self.toc, text=extract_text(doc))

    def children(self, node: dict) -> str:
        return "".join(self.node(child) for child in node.get("content") or [])

    def node(self, node: dict) -> str:
        kind = node.get("type")
        method = getattr(self, f"render_{kind}", None)
        if method is None:
            # Unknown node: keep its content readable rather than dropping it.
            return self.children(node)
        return method(node)

    # Inline

    def render_text(self, node: dict) -> str:
        html = escape(node.get("text", ""), quote=False)
        for mark in node.get("marks") or []:
            html = self.mark(mark, html)
        return html

    def mark(self, mark: dict, html: str) -> str:
        kind = mark.get("type")
        attrs = mark.get("attrs") or {}
        match kind:
            case "bold":
                return f"<strong>{html}</strong>"
            case "italic":
                return f"<em>{html}</em>"
            case "underline":
                return f"<u>{html}</u>"
            case "strike":
                return f"<s>{html}</s>"
            case "code":
                return f"<code>{html}</code>"
            case "highlight":
                return f"<mark>{html}</mark>"
            case "subscript":
                return f"<sub>{html}</sub>"
            case "superscript":
                return f"<sup>{html}</sup>"
            case "link":
                href = safe_url(attrs.get("href"))
                if href is None:
                    return html
                external = href.startswith(("http://", "https://"))
                rel = ' target="_blank" rel="noopener noreferrer"' if external else ""
                return f'<a href="{attr(href)}"{rel}>{html}</a>'
        return html

    def render_hardBreak(self, node: dict) -> str:
        return "<br>"

    def render_image(self, node: dict) -> str:
        attrs = node.get("attrs") or {}
        src = safe_url(attrs.get("src"))
        if src is None:
            return ""
        alt = attr(attrs.get("alt") or "")
        title = attrs.get("title")
        title_attr = f' title="{attr(title)}"' if title else ""
        image = f'<img src="{attr(src)}" alt="{alt}"{title_attr} loading="lazy">'
        if title:
            return f"<figure>{image}<figcaption>{escape(title)}</figcaption></figure>"
        return f"<figure>{image}</figure>"

    # Blocks

    def text_align(self, node: dict) -> str:
        align = (node.get("attrs") or {}).get("textAlign")
        if align in {"center", "right", "justify"}:
            return f' style="text-align: {align}"'
        return ""

    def render_paragraph(self, node: dict) -> str:
        return f"<p{self.text_align(node)}>{self.children(node)}</p>"

    def render_heading(self, node: dict) -> str:
        level = (node.get("attrs") or {}).get("level", 2)
        try:
            level = min(max(int(level), 1), 6)
        except TypeError, ValueError:
            level = 2
        title = extract_text(node).strip()
        anchor = self.unique_id(slugify(title) or "section")
        if level in TOC_LEVELS and title:
            self.toc.append({"id": anchor, "title": title, "level": level})
        return (
            f'<h{level} id="{anchor}"{self.text_align(node)}>{self.children(node)}'
            f'<a class="heading-anchor" href="#{anchor}" aria-hidden="true">#</a></h{level}>'
        )

    def unique_id(self, base: str) -> str:
        candidate = base
        counter = 2
        while candidate in self.used_ids:
            candidate = f"{base}-{counter}"
            counter += 1
        self.used_ids.add(candidate)
        return candidate

    def render_blockquote(self, node: dict) -> str:
        return f"<blockquote>{self.children(node)}</blockquote>"

    def render_horizontalRule(self, node: dict) -> str:
        return "<hr>"

    def render_codeBlock(self, node: dict) -> str:
        language = (node.get("attrs") or {}).get("language") or ""
        code = escape("".join(child.get("text", "") for child in node.get("content") or []))
        class_attr = f' class="language-{attr(language)}"' if language else ""
        label = f'<span class="code-language">{escape(language)}</span>' if language else ""
        return f'<div class="code-block">{label}<pre><code{class_attr}>{code}</code></pre></div>'

    def render_bulletList(self, node: dict) -> str:
        return f"<ul>{self.children(node)}</ul>"

    def render_orderedList(self, node: dict) -> str:
        start = (node.get("attrs") or {}).get("start", 1)
        start_attr = f' start="{int(start)}"' if isinstance(start, int) and start != 1 else ""
        return f"<ol{start_attr}>{self.children(node)}</ol>"

    def render_listItem(self, node: dict) -> str:
        return f"<li>{self.children(node)}</li>"

    def render_taskList(self, node: dict) -> str:
        return f'<ul class="task-list">{self.children(node)}</ul>'

    def render_taskItem(self, node: dict) -> str:
        checked = " checked" if (node.get("attrs") or {}).get("checked") else ""
        return (
            f'<li class="task-item"><input type="checkbox" disabled{checked}>'
            f"<div>{self.children(node)}</div></li>"
        )

    def render_callout(self, node: dict) -> str:
        variant = (node.get("attrs") or {}).get("variant", "info")
        if variant not in CALLOUT_VARIANTS:
            variant = "info"
        icon = CALLOUT_ICONS[variant]
        return (
            f'<div class="callout callout-{variant}">'
            f'<i class="callout-icon fa-solid {icon}" aria-hidden="true"></i>'
            f'<div class="callout-content">{self.children(node)}</div></div>'
        )

    def render_table(self, node: dict) -> str:
        return f'<div class="table-wrapper"><table>{self.children(node)}</table></div>'

    def render_tableRow(self, node: dict) -> str:
        return f"<tr>{self.children(node)}</tr>"

    def cell(self, tag: str, node: dict) -> str:
        attrs = node.get("attrs") or {}
        extra = ""
        for name in ("colspan", "rowspan"):
            value = attrs.get(name)
            if isinstance(value, int) and value > 1:
                extra += f' {name}="{value}"'
        return f"<{tag}{extra}>{self.children(node)}</{tag}>"

    def render_tableHeader(self, node: dict) -> str:
        return self.cell("th", node)

    def render_tableCell(self, node: dict) -> str:
        return self.cell("td", node)


BLOCK_TYPES = {
    "paragraph",
    "heading",
    "blockquote",
    "codeBlock",
    "listItem",
    "taskItem",
    "tableRow",
    "callout",
    "horizontalRule",
}


def extract_text(node: dict) -> str:
    """Plain text of a document, used for search and excerpts."""
    parts: list[str] = []

    def walk(current: dict):
        kind = current.get("type")
        if kind == "text":
            parts.append(current.get("text", ""))
            return
        if kind == "hardBreak":
            parts.append("\n")
            return
        if kind == "image":
            alt = (current.get("attrs") or {}).get("alt")
            if alt:
                parts.append(alt)
            return
        for child in current.get("content") or []:
            walk(child)
        if kind in BLOCK_TYPES:
            parts.append("\n")
        elif kind in {"tableCell", "tableHeader"}:
            parts.append(" ")

    walk(node or {})
    lines = [" ".join(line.split()) for line in "".join(parts).split("\n")]
    return "\n".join(line for line in lines if line)


def render_document(doc: dict | None) -> RenderResult:
    return Renderer().render(doc)


def excerpt(text: str, length: int = 200) -> str:
    flat = " ".join(text.split())
    if len(flat) <= length:
        return flat
    return flat[:length].rsplit(" ", 1)[0] + "…"
