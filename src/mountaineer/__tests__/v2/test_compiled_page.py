from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse

from mountaineer.v2.page.compiled import CompiledPage
from mountaineer.v2.page.core import Page


@pytest.mark.asyncio
async def test_compiled_page_get_html_response() -> None:
    page = Page(view=Path("views/Post.tsx"), path="/post")
    compiled = CompiledPage(
        page=page,
        server_js="server",
        client_js="client",
        ssr_timeout=7,
    )

    request = Request(scope={"type": "http", "path": "/post", "headers": []})

    with (
        patch("mountaineer.v2.page.compiled.resolve_data") as mock_resolve,
        patch("mountaineer.v2.page_renderer.mountaineer_rs.render_ssr") as mock_render,
    ):
        mock_resolve.return_value = {"foo": "bar"}
        mock_render.return_value = "<span>SSR</span>"

        response = await compiled.get(request)

    assert isinstance(response, HTMLResponse)
    assert response.status_code == 200
    assert '<div id="root"><span>SSR</span></div>' in response.body.decode()
    # Check data injection
    assert 'window.__DATA__ = {"foo": "bar"};' in response.body.decode()

    mock_resolve.assert_called_once()
    assert mock_resolve.call_args.kwargs["definitions"] == []  # No data registered


def test_compiled_page_router_structure() -> None:
    page = Page(view=Path("views/Post.tsx"), path="/post")

    @page.data(ssr=True)
    async def loader1():
        return 1

    @page.data(ssr=False, expose=False)
    async def loader2():
        return 2

    @page.action()
    async def action1():
        return 3

    compiled = CompiledPage(
        page=page,
        server_js="server",
        client_js="client",
        ssr_timeout=7,
    )

    router = compiled(path=page.path)

    # Routes expected:
    # 1. GET /post (Main)
    # 2. GET /post/_data/loader1 (Exposed by default)
    # 3. POST /post/_action/action1

    # loader2 is expose=False, so no route.

    routes = router.routes
    assert len(routes) == 3

    paths = {getattr(r, "path", "") for r in routes}
    assert paths == {
        "/post",
        "/post/_data/loader1",
        "/post/_action/action1",
    }


@pytest.mark.asyncio
async def test_data_endpoint() -> None:
    page = Page(view=Path("views/Post.tsx"), path="/post")

    @page.data(ssr=True)
    async def loader1():
        return 1

    compiled = CompiledPage(
        page=page,
        server_js="server",
        client_js="client",
        ssr_timeout=7,
    )

    request = Request(scope={"type": "http", "path": "/post/_data/loader1", "headers": []})

    with patch("mountaineer.v2.page.compiled.resolve_data") as mock_resolve:
        mock_resolve.return_value = {"loader1": 99}

        response = await compiled.data_endpoint(name="loader1", request=request)

    assert isinstance(response, JSONResponse)
    import json

    body = json.loads(response.body)
    assert body == {"data": {"loader1": 99}}


@pytest.mark.asyncio
async def test_action_endpoint() -> None:
    page = Page(view=Path("views/Post.tsx"), path="/post")

    @page.data(ssr=True)
    async def loader1():
        return 1

    @page.action(update=(loader1,))
    async def action1():
        return "ok"

    compiled = CompiledPage(
        page=page,
        server_js="server",
        client_js="client",
        ssr_timeout=7,
    )

    request = Request(scope={"type": "http", "path": "/post/_action/action1", "headers": []})

    with (
        patch("mountaineer.v2.page.compiled.resolve_action") as mock_resolve_action,
        patch("mountaineer.v2.page.compiled.resolve_data") as mock_resolve_data,
    ):
        mock_resolve_action.return_value = "ok"
        mock_resolve_data.return_value = {"loader1": 100}

        response = await compiled.action_endpoint(name="action1", request=request)

    import json

    body = json.loads(response.body)
    assert body == {
        "action": "ok",
        "data": {"loader1": 100},
    }
