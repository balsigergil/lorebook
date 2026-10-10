"""Markdown import and export.

Markdown is only an exchange format: imports become Tiptap JSON documents,
and exports serialise the JSON back to Markdown (CommonMark + GFM tables,
strikethrough and task lists; callouts use GitHub alert syntax).
"""

import re

from markdown_it import MarkdownIt
from markdown_it.token import Token

ALERTS = {
    "NOTE": "info",
    "TIP": "success",
    "IMPORTANT": "info",
    "WARNING": "warning",
    "CAUTION": "danger",
}
ALERT_FOR_VARIANT = {"info": "NOTE", "success": "TIP", "warning": "WARNING", "danger": "CAUTION"}
ALERT_RE = re.compile(r"^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*")
TASK_RE = re.compile(r"^\[([ xX])\]\s+")
FRONT_MATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)

BLOCK_OPEN = {
    "paragraph_open": "paragraph",
    "heading_open": "heading",
    "blockquote_open": "blockquote",
    "bullet_list_open": "bulletList",
    "ordered_list_open": "orderedList",
    "list_item_open": "listItem",
    "table_open": "table",
    "tr_open": "tableRow",
    "th_open": "tableHeader",
    "td_open": "tableCell",
}

MARK_OPEN = {
    "strong_open": "bold",
    "em_open": "italic",
    "s_open": "strike",
    "link_open": "link",
}


def _parser() -> MarkdownIt:
    return MarkdownIt("commonmark", {"html": False}).enable(["table", "strikethrough"])


# Import


def markdown_to_doc(source: str) -> tuple[str, dict]:
    """Convert Markdown to a Tiptap document. Returns (title, doc).

    The title is taken from front matter (`title:`) or from a leading H1,
    which is then removed from the body.
    """
    title = ""
    front = FRONT_MATTER_RE.match(source)
    if front:
        for line in front.group(0).splitlines():
            if line.lower().startswith("title:"):
                title = line.split(":", 1)[1].strip().strip("\"'")
        source = source[front.end() :]

    tokens = _parser().parse(source)
    content = _blocks(tokens)

    if content and content[0]["type"] == "heading" and content[0]["attrs"]["level"] == 1:
        heading = content.pop(0)
        if not title:
            title = "".join(child.get("text", "") for child in heading.get("content", []))
    content = [_upgrade_blockquote(node) for node in content]
    content = [_upgrade_task_list(node) for node in content]
    if not content:
        content = [{"type": "paragraph"}]
    return title.strip(), {"type": "doc", "content": content}


def _blocks(tokens: list[Token]) -> list[dict]:
    root: dict = {"type": "doc", "content": []}
    stack = [root]

    def push(node: dict):
        stack[-1].setdefault("content", []).append(node)

    for token in tokens:
        if token.type in BLOCK_OPEN:
            node: dict = {"type": BLOCK_OPEN[token.type]}
            if token.type == "heading_open":
                node["attrs"] = {"level": int(token.tag[1])}
            elif token.type == "ordered_list_open":
                start = token.attrGet("start")
                node["attrs"] = {"start": int(start) if start else 1}
            push(node)
            stack.append(node)
        elif token.type.endswith("_close") and token.type.replace("_close", "_open") in BLOCK_OPEN:
            node = stack.pop()
            if node["type"] in {"tableHeader", "tableCell"}:
                inline = node.pop("content", [])
                node["content"] = (
                    [{"type": "paragraph", "content": inline}]
                    if inline
                    else [{"type": "paragraph"}]
                )
            if node["type"] == "listItem" and not node.get("content"):
                node["content"] = [{"type": "paragraph"}]
        elif token.type in {"thead_open", "thead_close", "tbody_open", "tbody_close"}:
            continue
        elif token.type == "inline":
            inline = _inline(token.children or [])
            parent = stack[-1]
            if inline:
                parent.setdefault("content", []).extend(inline)
            if parent["type"] == "listItem":
                # Tight lists have no paragraph tokens.
                parent["content"] = [{"type": "paragraph", "content": parent.pop("content")}]
        elif token.type in {"fence", "code_block"}:
            language = (token.info or "").strip().split(" ")[0]
            code = token.content[:-1] if token.content.endswith("\n") else token.content
            node = {"type": "codeBlock", "attrs": {"language": language or None}}
            if code:
                node["content"] = [{"type": "text", "text": code}]
            push(node)
        elif token.type == "hr":
            push({"type": "horizontalRule"})
    _hoist_images(root)
    return root.get("content", [])


def _inline(tokens: list[Token]) -> list[dict]:
    nodes: list[dict] = []
    marks: list[dict] = []
    for token in tokens:
        if token.type in MARK_OPEN:
            mark: dict = {"type": MARK_OPEN[token.type]}
            if token.type == "link_open":
                mark["attrs"] = {"href": token.attrGet("href")}
            marks.append(mark)
        elif token.type.endswith("_close") and token.type.replace("_close", "_open") in MARK_OPEN:
            wanted = MARK_OPEN[token.type.replace("_close", "_open")]
            for index in range(len(marks) - 1, -1, -1):
                if marks[index]["type"] == wanted:
                    marks.pop(index)
                    break
        elif token.type in {"text", "html_inline"}:
            _append_text(nodes, token.content, marks)
        elif token.type == "code_inline":
            _append_text(nodes, token.content, [*marks, {"type": "code"}])
        elif token.type == "softbreak":
            _append_text(nodes, " ", marks)
        elif token.type == "hardbreak":
            nodes.append({"type": "hardBreak"})
        elif token.type == "image":
            nodes.append(
                {
                    "type": "image",
                    "attrs": {
                        "src": token.attrGet("src"),
                        "alt": token.content or None,
                        "title": token.attrGet("title"),
                    },
                }
            )
    return nodes


def _append_text(nodes: list[dict], text: str, marks: list[dict]):
    if not text:
        return
    copied = [dict(mark) for mark in marks]
    previous = nodes[-1] if nodes else None
    if previous and previous.get("type") == "text" and previous.get("marks", []) == copied:
        previous["text"] += text
        return
    node: dict = {"type": "text", "text": text}
    if copied:
        node["marks"] = copied
    nodes.append(node)


def _hoist_images(node: dict):
    """Images are block nodes in the editor: lift them out of paragraphs."""
    children = node.get("content")
    if not children:
        return
    result = []
    for child in children:
        _hoist_images(child)
        if child.get("type") == "paragraph" and any(
            grandchild.get("type") == "image" for grandchild in child.get("content", [])
        ):
            buffer: list[dict] = []
            for grandchild in child["content"]:
                if grandchild.get("type") == "image":
                    if any(item.get("text", "").strip() for item in buffer):
                        result.append({"type": "paragraph", "content": buffer})
                    buffer = []
                    result.append(grandchild)
                else:
                    buffer.append(grandchild)
            if any(item.get("text", "").strip() for item in buffer):
                result.append({"type": "paragraph", "content": buffer})
        else:
            result.append(child)
    node["content"] = result


def _upgrade_blockquote(node: dict) -> dict:
    """Turn GitHub alerts (`> [!NOTE]`) into callouts."""
    if node.get("type") != "blockquote":
        return node
    first = (node.get("content") or [None])[0]
    if not first or first.get("type") != "paragraph" or not first.get("content"):
        return node
    text_node = first["content"][0]
    if text_node.get("type") != "text":
        return node
    match = ALERT_RE.match(text_node["text"])
    if not match:
        return node
    text_node["text"] = text_node["text"][match.end() :].lstrip()
    if not text_node["text"]:
        first["content"].pop(0)
    content = [child for child in node["content"] if child.get("content") or child is not first]
    return {
        "type": "callout",
        "attrs": {"variant": ALERTS[match.group(1)]},
        "content": content or [{"type": "paragraph"}],
    }


def _upgrade_task_list(node: dict) -> dict:
    """Turn `- [ ] item` lists into task lists."""
    for child in node.get("content") or []:
        _upgrade_task_list(child)
    if node.get("type") != "bulletList":
        return node
    items = node.get("content") or []
    checks = []
    for item in items:
        paragraph = (item.get("content") or [{}])[0]
        first = (paragraph.get("content") or [{}])[0]
        match = TASK_RE.match(first.get("text", "")) if first.get("type") == "text" else None
        if not match:
            return node
        checks.append((item, first, match))
    if not checks:
        return node
    for item, first, match in checks:
        first["text"] = first["text"][match.end() :]
        item["type"] = "taskItem"
        item["attrs"] = {"checked": match.group(1).lower() == "x"}
    node["type"] = "taskList"
    return node


# Export


def doc_to_markdown(doc: dict | None, title: str = "") -> str:
    blocks = _md_blocks((doc or {}).get("content") or [])
    body = "\n\n".join(block for block in blocks if block is not None).strip()
    if title:
        return f"# {title}\n\n{body}\n" if body else f"# {title}\n"
    return f"{body}\n" if body else ""


def _md_blocks(nodes: list[dict]) -> list[str]:
    return [_md_block(node) for node in nodes]


def _indent(text: str, prefix: str, first: str | None = None) -> str:
    lines = text.split("\n")
    first_prefix = prefix if first is None else first
    return "\n".join(
        (first_prefix if index == 0 else prefix) + line if line else line.rstrip()
        for index, line in enumerate(lines)
    )


def _md_block(node: dict) -> str:
    kind = node.get("type")
    attrs = node.get("attrs") or {}
    content = node.get("content") or []
    match kind:
        case "paragraph":
            return _md_inline(content)
        case "heading":
            return "#" * int(attrs.get("level", 2)) + " " + _md_inline(content)
        case "blockquote":
            inner = "\n\n".join(_md_blocks(content))
            return _indent(inner, "> ").replace("\n\n", "\n>\n")
        case "callout":
            alert = ALERT_FOR_VARIANT.get(attrs.get("variant", "info"), "NOTE")
            inner = "\n\n".join(_md_blocks(content))
            return _indent(f"[!{alert}]\n{inner}", "> ").replace("\n\n", "\n>\n")
        case "codeBlock":
            code = "".join(child.get("text", "") for child in content)
            fence = "````" if "```" in code else "```"
            return f"{fence}{attrs.get('language') or ''}\n{code}\n{fence}"
        case "horizontalRule":
            return "---"
        case "bulletList" | "orderedList" | "taskList":
            return _md_list(node)
        case "image":
            return _md_image(attrs)
        case "table":
            return _md_table(node)
    return "\n\n".join(_md_blocks(content))


def _md_list(node: dict) -> str:
    kind = node["type"]
    start = (node.get("attrs") or {}).get("start", 1) or 1
    items = []
    for index, item in enumerate(node.get("content") or []):
        if kind == "orderedList":
            marker = f"{start + index}. "
        elif kind == "taskList":
            checked = (item.get("attrs") or {}).get("checked")
            marker = f"- [{'x' if checked else ' '}] "
        else:
            marker = "- "
        inner = "\n\n".join(_md_blocks(item.get("content") or []))
        pad = " " * (len(marker) if kind != "taskList" else 2)
        items.append(_indent(inner, pad, first=marker))
    return "\n".join(items)


def _md_image(attrs: dict) -> str:
    title = attrs.get("title")
    title_part = f' "{title}"' if title else ""
    return f"![{attrs.get('alt') or ''}]({attrs.get('src') or ''}{title_part})"


def _md_table(node: dict) -> str:
    rows = []
    for row in node.get("content") or []:
        cells = []
        for cell in row.get("content") or []:
            text = " ".join(_md_blocks(cell.get("content") or []))
            cells.append(text.replace("|", "\\|").replace("\n", " "))
        rows.append(cells)
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "| " + " | ".join(["---"] * width) + " |"]
    lines += ["| " + " | ".join(row) + " |" for row in rows[1:]]
    return "\n".join(lines)


MARK_ORDER = ["link", "bold", "italic", "strike", "code"]


def _escape(text: str) -> str:
    return re.sub(r"([\\`*_\[\]<>])", r"\\\1", text)


def _md_inline(nodes: list[dict]) -> str:
    out = []
    for node in nodes:
        kind = node.get("type")
        if kind == "hardBreak":
            out.append("\\\n")
            continue
        if kind == "image":
            out.append(_md_image(node.get("attrs") or {}))
            continue
        if kind != "text":
            continue
        marks = {mark.get("type"): mark for mark in node.get("marks") or []}
        text = node.get("text", "")
        if "code" in marks:
            tick = "``" if "`" in text else "`"
            text = f"{tick}{text}{tick}"
        else:
            text = _escape(text)
        if "italic" in marks:
            text = f"*{text}*"
        if "bold" in marks:
            text = f"**{text}**"
        if "strike" in marks:
            text = f"~~{text}~~"
        if "link" in marks:
            href = (marks["link"].get("attrs") or {}).get("href") or ""
            text = f"[{text}]({href})"
        out.append(text)
    return "".join(out)
