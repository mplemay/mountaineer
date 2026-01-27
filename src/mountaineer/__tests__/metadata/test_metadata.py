from pathlib import Path

from mountaineer import LinkAttribute, MetaAttribute, Metadata, Mountaineer, ScriptAttribute


def test_metadata_merge_precedence():
    app = Mountaineer(view_root=Path())

    global_metadata = Metadata(
        title="Global",
        metas=[MetaAttribute(name="description", content="global")],
        links=[LinkAttribute(rel="icon", href="/global.ico")],
        scripts=[ScriptAttribute(src="/global.js")],
    )
    app.global_metadata = global_metadata

    layout_metadata = Metadata(
        title="Layout",
        metas=[MetaAttribute(name="description", content="layout")],
        links=[LinkAttribute(rel="icon", href="/layout.ico")],
        scripts=[ScriptAttribute(src="/layout.js")],
    )

    page_metadata = Metadata(
        title="Page",
        metas=[MetaAttribute(name="description", content="page")],
        links=[LinkAttribute(rel="stylesheet", href="/page.css")],
        scripts=[ScriptAttribute(src="/page.js")],
    )

    merged = app._merge_metadata_chain(
        metadata_chain=[layout_metadata, page_metadata],
        include_global=True,
    )

    assert merged is not None
    assert merged.title == "Page"
    assert [meta.content for meta in merged.metas] == ["page"]
    assert [link.href for link in merged.links] == [
        "/global.ico",
        "/layout.ico",
        "/page.css",
    ]
    assert [script.src for script in merged.scripts] == [
        "/global.js",
        "/layout.js",
        "/page.js",
    ]
