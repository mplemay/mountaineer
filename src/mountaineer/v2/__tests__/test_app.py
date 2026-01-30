from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mountaineer.v2 import Mountaineer, Page, Settings


@pytest.mark.usefixtures("mock_ssr")
def test_mountaineer_include_page(mock_bundler, tmp_path):
    """
    Test registering a page and routing to it.
    """
    settings = Settings(
        view_root=tmp_path,
        node_modules_path=tmp_path,
    )
    app = Mountaineer(settings=settings)

    # Create dummy view file to avoid path errors if checked (though bundler is mocked)
    # The bundler code resolves path relative to view_root, but the mock intercepts it.

    page = Page(view=Path("home.tsx"), path="/home")
    app.include_page(page=page)

    # Mount to test client
    fastapi_app = FastAPI()
    fastapi_app.mount("/", app)

    client = TestClient(fastapi_app)
    response = client.get("/home")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert '<div id="root">' in response.text

    # Verify compilation happened
    assert mock_bundler.compile_independent_bundles.call_count == 2


@pytest.mark.usefixtures("mock_bundler")
def test_mountaineer_duplicate_path(tmp_path):
    settings = Settings(view_root=tmp_path, node_modules_path=tmp_path)
    app = Mountaineer(settings=settings)

    page1 = Page(view=Path("a.tsx"), path="/same")
    page2 = Page(view=Path("b.tsx"), path="/same")

    app.include_page(page=page1)

    with pytest.raises(ValueError, match="Page path already registered"):
        app.include_page(page=page2)
