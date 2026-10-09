from apps.content.rendering import excerpt, extract_text, render_document, safe_url


def test_renders_marks_headings_and_toc():
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "heading",
                "attrs": {"level": 2},
                "content": [{"type": "text", "text": "Install"}],
            },
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Run "},
                    {"type": "text", "text": "uv sync", "marks": [{"type": "code"}]},
                    {
                        "type": "text",
                        "text": " now",
                        "marks": [{"type": "bold"}, {"type": "italic"}],
                    },
                ],
            },
            {
                "type": "heading",
                "attrs": {"level": 3},
                "content": [{"type": "text", "text": "Install"}],
            },
        ],
    }
    result = render_document(doc)
    assert '<h2 id="install">Install' in result.html
    assert '<h3 id="install-2">' in result.html
    assert "<code>uv sync</code>" in result.html
    assert "<em><strong> now</strong></em>" in result.html
    assert result.toc == [
        {"id": "install", "title": "Install", "level": 2},
        {"id": "install-2", "title": "Install", "level": 3},
    ]


def test_escapes_text_and_rejects_unsafe_links():
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "<script>alert(1)</script>"},
                    {
                        "type": "text",
                        "text": "click",
                        "marks": [{"type": "link", "attrs": {"href": "javascript:alert(1)"}}],
                    },
                ],
            },
            {"type": "image", "attrs": {"src": "javascript:alert(1)", "alt": "x"}},
        ],
    }
    html = render_document(doc).html
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "javascript:" not in html
    assert "<img" not in html


def test_external_links_open_in_new_tab():
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": "site",
                        "marks": [{"type": "link", "attrs": {"href": "https://example.com"}}],
                    }
                ],
            }
        ],
    }
    assert 'target="_blank" rel="noopener noreferrer"' in render_document(doc).html


def test_blocks():
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "callout",
                "attrs": {"variant": "warning"},
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "Careful"}]}
                ],
            },
            {
                "type": "codeBlock",
                "attrs": {"language": "python"},
                "content": [{"type": "text", "text": "print('<hi>')"}],
            },
            {
                "type": "table",
                "content": [
                    {
                        "type": "tableRow",
                        "content": [
                            {
                                "type": "tableHeader",
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "content": [{"type": "text", "text": "A"}],
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "type": "tableRow",
                        "content": [
                            {
                                "type": "tableCell",
                                "attrs": {"colspan": 2},
                                "content": [{"type": "paragraph"}],
                            },
                        ],
                    },
                ],
            },
            {
                "type": "taskList",
                "content": [
                    {
                        "type": "taskItem",
                        "attrs": {"checked": True},
                        "content": [
                            {"type": "paragraph", "content": [{"type": "text", "text": "Done"}]}
                        ],
                    }
                ],
            },
            {"type": "mysteryNode", "content": [{"type": "text", "text": "kept"}]},
        ],
    }
    html = render_document(doc).html
    assert 'class="callout callout-warning"' in html
    assert '<code class="language-python">print(&#x27;&lt;hi&gt;&#x27;)</code>' in html
    assert "<th>" in html and 'colspan="2"' in html
    assert "checked" in html
    assert "kept" in html


def test_extract_text_and_excerpt():
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "heading",
                "attrs": {"level": 2},
                "content": [{"type": "text", "text": "Title"}],
            },
            {"type": "paragraph", "content": [{"type": "text", "text": "Hello   world"}]},
        ],
    }
    assert extract_text(doc) == "Title\nHello world"
    assert excerpt("word " * 100, 20).endswith("…")


def test_safe_url():
    assert safe_url("/files/x.png") == "/files/x.png"
    assert safe_url("#anchor") == "#anchor"
    assert safe_url("mailto:a@b.c") == "mailto:a@b.c"
    assert safe_url("vbscript:x") is None
    assert safe_url("data:text/html,x") is None
