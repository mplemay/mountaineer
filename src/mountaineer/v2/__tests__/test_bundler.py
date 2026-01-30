from pathlib import Path

from mountaineer.v2.bundler import Bundler
from mountaineer.v2.settings import Settings


def test_bundler_compilation_flow(mock_bundler, tmp_path):
    """
    Test that bundler calls the rust core with correct parameters.
    """
    settings = Settings(
        view_root=tmp_path / "views",
        node_modules_path=tmp_path / "node_modules",
        PRODUCTION=False,
        live_reload_port=3000,
    )

    bundler = Bundler(settings=settings)
    view_path = Path("page.tsx")  # Relative to view_root

    result = bundler.compile(view_path=view_path)

    # Check result content
    # Since mock returns the same tuple (["const server..."], "map")
    # and compile calls take the first element [0], both will be "const server..."
    assert result.server_js == "const server = 'server_bundle';"
    assert result.client_js == "const server = 'server_bundle';"

    # Check calls to mock
    # We expect 2 calls: one for server, one for client
    assert mock_bundler.compile_independent_bundles.call_count == 2

    # Inspect arguments of the first call (server)
    call_args_list = mock_bundler.compile_independent_bundles.call_args_list

    # Server call check
    # Note: Order might depend on implementation, but typically server then client or vice versa.
    # We'll check if we can find the calls we expect.

    server_calls = [c for c in call_args_list if c.kwargs.get("is_server") is True]
    client_calls = [c for c in call_args_list if c.kwargs.get("is_server") is False]

    assert len(server_calls) == 1
    assert len(client_calls) == 1

    # Validate resolved path
    expected_full_path = str(settings.view_root / view_path)

    _, server_kwargs = server_calls[0]
    assert server_kwargs["paths"] == [[expected_full_path]]
    assert server_kwargs["environment"] == "development"
    assert server_kwargs["live_reload_port"] == 3000
