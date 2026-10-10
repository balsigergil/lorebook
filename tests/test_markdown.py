from apps.content.markdown import doc_to_markdown, markdown_to_doc
from apps.content.rendering import render_document

SOURCE = """---
title: Getting started
---

Intro with **bold**, *italic*, `code` and a [link](https://example.com).

## Install

1. First
2. Second

- [x] Done
- [ ] Todo

> [!WARNING]
> Be careful.

```python
print("hi")
```

| Name | Value |
| --- | --- |
| a | b |

![Diagram](/files/abc/diagram.png "Architecture")

---
"""


def test_import_markdown():
    title, doc = markdown_to_doc(SOURCE)
    assert title == "Getting started"
    types = [node["type"] for node in doc["content"]]
    assert types == [
        "paragraph",
        "heading",
        "orderedList",
        "taskList",
        "callout",
        "codeBlock",
        "table",
        "image",
        "horizontalRule",
    ]
    paragraph = doc["content"][0]["content"]
    assert {"type": "text", "text": "bold", "marks": [{"type": "bold"}]} in paragraph
    assert doc["content"][4]["attrs"] == {"variant": "warning"}
    assert doc["content"][3]["content"][0]["attrs"] == {"checked": True}
    assert doc["content"][5]["attrs"]["language"] == "python"
    html = render_document(doc).html
    assert "<table>" in html and "callout-warning" in html


def test_leading_h1_becomes_title():
    title, doc = markdown_to_doc("# Hello\n\nWorld")
    assert title == "Hello"
    assert doc["content"][0]["type"] == "paragraph"


def test_round_trip():
    title, doc = markdown_to_doc(SOURCE)
    exported = doc_to_markdown(doc, title=title)
    assert exported.startswith("# Getting started\n")
    assert "**bold**" in exported
    assert "[link](https://example.com)" in exported
    assert "1. First" in exported
    assert "- [x] Done" in exported
    assert "> [!WARNING]" in exported
    assert '```python\nprint("hi")\n```' in exported
    assert "| Name | Value |" in exported
    assert '![Diagram](/files/abc/diagram.png "Architecture")' in exported
    _title, again = markdown_to_doc(exported)
    assert [node["type"] for node in again["content"]] == [node["type"] for node in doc["content"]]


def test_empty_document():
    title, doc = markdown_to_doc("")
    assert title == ""
    assert doc == {"type": "doc", "content": [{"type": "paragraph"}]}
