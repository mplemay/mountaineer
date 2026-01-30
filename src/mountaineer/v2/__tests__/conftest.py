import sys
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(scope="session")
def example_path():
    """
    Add the example project to sys.path so we can import it for integration tests.
    """
    # src/mountaineer/v2/__tests__/conftest.py -> ../../../.. -> root
    repo_root = Path(__file__).parents[4]
    example_src = repo_root / "example" / "src"

    if not example_src.exists():
        pytest.fail(f"Example src directory not found at {example_src}")

    str_example_src = str(example_src)
    if str_example_src not in sys.path:
        sys.path.insert(0, str_example_src)

    return example_src


@pytest.fixture
def mock_bundler():
    """
    Mock the Rust core bundler interactions.
    """
    with patch("mountaineer.v2.bundler.mountaineer_rs") as mock_core:
        # Return dummy JS for server and client
        # compile_independent_bundles returns (Vec<String>, SourceMap)
        mock_core.compile_independent_bundles.return_value = (
            ["const server = 'server_bundle';"],
            "map_content",
        )
        yield mock_core


@pytest.fixture
def mock_ssr():
    """
    Mock the Rust core SSR rendering.
    """
    with patch("mountaineer.v2.page_renderer.mountaineer_rs") as mock_core:
        mock_core.render_ssr.return_value = "<div id='ssr-content'>Hello World</div>"
        yield mock_core
