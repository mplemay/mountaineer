from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from pytest import raises

from mountaineer.v2.app import Mountaineer
from mountaineer.v2.bundler import BundleResult
from mountaineer.v2.page.core import Page
from mountaineer.v2.settings import Settings


def test_mountaineer_include_page_registers_route() -> None:
    settings = Settings(view_root=Path("views"), node_modules_path=Path("node_modules"))
    mountaineer = Mountaineer(settings=settings)
    page = Page(view=Path("views/Post.tsx"), path="/post/{post_id}")

    def fake_compile(*, view_path: Path) -> BundleResult:
        return BundleResult(client_js="client", server_js="server")

    mountaineer._bundler.compile = fake_compile

    mountaineer.include_page(page=page)

    paths = [route.path for route in mountaineer._app.routes]
    assert "/post/{post_id}" in paths


def test_mountaineer_rejects_duplicate_paths() -> None:
    settings = Settings(view_root=Path("views"), node_modules_path=Path("node_modules"))
    mountaineer = Mountaineer(settings=settings)
    page = Page(view=Path("views/Post.tsx"), path="/post/{post_id}")

    def fake_compile(*, view_path: Path) -> BundleResult:
        return BundleResult(client_js="client", server_js="server")

    mountaineer._bundler.compile = fake_compile

    mountaineer.include_page(page=page)

    with raises(ValueError):
        mountaineer.include_page(page=page)


def test_mountaineer_asgi_dispatch() -> None:
    settings = Settings(view_root=Path("views"), node_modules_path=Path("node_modules"))
    mountaineer = Mountaineer(settings=settings)
    page = Page(view=Path("views/Post.tsx"), path="/post/{post_id}")

    def fake_compile(*, view_path: Path) -> BundleResult:
        return BundleResult(client_js="client", server_js="server")

    mountaineer._bundler.compile = fake_compile

    with patch("mountaineer.v2.html.mountaineer_rs.render_ssr") as mock_render:
        mock_render.return_value = "<span>SSR</span>"
        mountaineer.include_page(page=page)

        client = TestClient(app=mountaineer)
        response = client.get("/post/123")

    assert response.status_code == 200
    assert "<span>SSR</span>" in response.text
    assert "<script type=\"module\">client</script>" in response.text
