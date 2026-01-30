from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from mountaineer.v2.app import Mountaineer
from mountaineer.v2.page.core import Page
from mountaineer.v2.settings import Settings


class PostParams(BaseModel):
    slug: str


@pytest.mark.integration_tests
def test_v2_integration_data_and_actions() -> None:
    settings = Settings(view_root=Path("views"), node_modules_path=Path("node_modules"))
    mountaineer = Mountaineer(settings=settings)

    page = Page(view=Path("views/Post.tsx"), path="/post/{slug}", params=PostParams)

    @page.data(ssr=True)
    async def get_post(params: PostParams) -> dict:
        return {"slug": params.slug, "title": "Hello"}

    @page.data(ssr=False)
    async def get_comments(params: PostParams) -> list[str]:
        return ["first", params.slug]

    @page.action(update=(get_post,))
    async def upvote(_params: PostParams) -> int:
        return 1

    with (
        patch("mountaineer.v2.bundler.mountaineer_rs.compile_independent_bundles") as mock_compile,
        patch("mountaineer.v2.page_renderer.mountaineer_rs.render_ssr") as mock_render,
    ):
        # Bundler is called twice: once for server, once for client
        mock_compile.side_effect = [
            (["server_js"], ["server_map"]),
            (["client_js"], ["client_map"]),
        ]
        mock_render.return_value = "<span>SSR Content</span>"

        mountaineer.include_page(page=page)

        client = TestClient(mountaineer)

        # 1. SSR GET
        response = client.get("/post/my-slug")
        assert response.status_code == 200
        assert "<span>SSR Content</span>" in response.text
        # Check data injection
        assert '"slug": "my-slug"' in response.text
        assert '"title": "Hello"' in response.text
        # Non-SSR data should NOT be there
        assert '"first"' not in response.text

        # 2. Data Endpoint
        response = client.get("/post/my-slug/_data/get_comments")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["get_comments"] == ["first", "my-slug"]

        # 3. Action Endpoint
        response = client.post("/post/my-slug/_action/upvote")
        assert response.status_code == 200
        body = response.json()
        assert body["action"] == 1
        assert body["data"]["get_post"] == {"slug": "my-slug", "title": "Hello"}
