from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mountaineer.v2.app import Mountaineer
from mountaineer.v2.page.core import Page
from mountaineer.v2.settings import Settings


@pytest.mark.integration_tests
def test_v2_integration_multiple_pages() -> None:
    settings = Settings(view_root=Path("views"), node_modules_path=Path("node_modules"))
    mountaineer = Mountaineer(settings=settings)

    page_one = Page(view=Path("views/Post.tsx"), path="/post/{post_id}")
    page_two = Page(view=Path("views/About.tsx"), path="/about")

    with (
        patch(
            "mountaineer.v2.bundler.mountaineer_rs.compile_independent_bundles",
        ) as mock_compile,
        patch(
            "mountaineer.v2.html.mountaineer_rs.render_ssr",
        ) as mock_render,
    ):
        mock_compile.side_effect = [
            (["server_js_1"], ["server_map_1"]),
            (["client_js_1"], ["client_map_1"]),
            (["server_js_2"], ["server_map_2"]),
            (["client_js_2"], ["client_map_2"]),
        ]
        mock_render.side_effect = ["<span>SSR1</span>", "<span>SSR2</span>"]

        mountaineer.include_page(page=page_one)
        mountaineer.include_page(page=page_two)

        app = FastAPI()
        app.mount(path="/", app=mountaineer, name="website")
        client = TestClient(app=app)

        response_one = client.get("/post/123")
        response_two = client.get("/about")

    assert response_one.status_code == 200
    assert response_two.status_code == 200
    assert response_one.headers["content-type"].startswith("text/html")
    assert response_two.headers["content-type"].startswith("text/html")
    assert "<span>SSR1</span>" in response_one.text
    assert "<span>SSR2</span>" in response_two.text
    assert '<script type="module">client_js_1</script>' in response_one.text
    assert '<script type="module">client_js_2</script>' in response_two.text
    assert 'src="' not in response_one.text
    assert 'src="' not in response_two.text


@pytest.mark.integration_tests
def test_v2_integration_settings_do_not_block_routing() -> None:
    settings = Settings(
        view_root=Path("views"),
        node_modules_path=Path("node_modules"),
        PRODUCTION=True,
        live_reload_port=4000,
        public_path="/assets",
        ssr_timeout=5,
    )
    mountaineer = Mountaineer(settings=settings)

    page = Page(view=Path("views/Post.tsx"), path="/post/{post_id}")

    with (
        patch(
            "mountaineer.v2.bundler.mountaineer_rs.compile_independent_bundles",
        ) as mock_compile,
        patch(
            "mountaineer.v2.html.mountaineer_rs.render_ssr",
        ) as mock_render,
    ):
        mock_compile.side_effect = [
            (["server_js"], ["server_map"]),
            (["client_js"], ["client_map"]),
        ]
        mock_render.return_value = "<span>SSR</span>"

        mountaineer.include_page(page=page)

        app = FastAPI()
        app.mount(path="/", app=mountaineer, name="website")
        client = TestClient(app=app)

        response = client.get("/post/123")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<span>SSR</span>" in response.text
