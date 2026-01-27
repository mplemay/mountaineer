from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.responses import HTMLResponse

from mountaineer.v2.page.compiled import CompiledPage
from mountaineer.v2.page.core import Page


@pytest.mark.asyncio
async def test_compiled_page_get_html_response() -> None:
    page = Page(view=Path("views/Post.tsx"), path="/post/{post_id}")
    compiled = CompiledPage(
        page=page,
        server_js="server",
        client_js="client",
        ssr_timeout=7,
    )

    with patch("mountaineer.v2.page_renderer.mountaineer_rs.render_ssr") as mock_render:
        mock_render.return_value = "<span>SSR</span>"

        response = await compiled.get()

    assert isinstance(response, HTMLResponse)
    assert response.status_code == 200
    assert '<div id="root"><span>SSR</span></div>' in response.body.decode()
    assert "window.__DATA__" in response.body.decode()
    assert '<script type="module">client</script>' in response.body.decode()
    mock_render.assert_called_once_with("server", hard_timeout=7)


def test_compiled_page_router() -> None:
    page = Page(view=Path("views/Post.tsx"), path="/post/{post_id}")
    compiled = CompiledPage(
        page=page,
        server_js="server",
        client_js="client",
        ssr_timeout=7,
    )

    router = compiled(path=page.path)

    assert len(router.routes) == 1
    route = router.routes[0]
    assert getattr(route, "path", None) == "/post/{post_id}"
    assert "GET" in getattr(route, "methods", set())


@pytest.mark.asyncio
async def test_compiled_page_propagates_ssr_errors() -> None:
    page = Page(view=Path("views/Post.tsx"), path="/post/{post_id}")
    compiled = CompiledPage(
        page=page,
        server_js="server",
        client_js="client",
        ssr_timeout=7,
    )

    with (
        patch(
            "mountaineer.v2.page_renderer.mountaineer_rs.render_ssr",
            side_effect=ValueError("boom"),
        ),
        pytest.raises(ValueError, match="boom"),
    ):
        await compiled.get()
