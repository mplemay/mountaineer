from pathlib import Path
from unittest.mock import patch

from pytest import raises

from mountaineer.v2.bundler import BundleResult, Bundler
from mountaineer.v2.settings import Settings


def test_bundler_compiles_dev_bundle(tmp_path: Path) -> None:
    view_root = tmp_path / "views"
    view_root.mkdir()
    node_modules = tmp_path / "node_modules"
    node_modules.mkdir()

    settings = Settings(
        view_root=view_root,
        node_modules_path=node_modules,
        live_reload_port=123,
    )
    bundler = Bundler(settings=settings)

    expected_view_path = (view_root / "page.tsx").resolve()

    with patch(
        "mountaineer.v2.bundler.mountaineer_rs.compile_independent_bundles"
    ) as mock_compile:
        mock_compile.side_effect = [
            (["server_js"], ["server_map"]),
            (["client_js"], ["client_map"]),
        ]

        result = bundler.compile(view_path=Path("page.tsx"))

    assert isinstance(result, BundleResult)
    assert result.server_js == "server_js"
    assert result.client_js == "client_js"

    server_call = mock_compile.call_args_list[0]
    client_call = mock_compile.call_args_list[1]

    assert server_call.kwargs["paths"] == [[str(expected_view_path)]]
    assert server_call.kwargs["environment"] == "development"
    assert server_call.kwargs["live_reload_port"] == 123
    assert server_call.kwargs["node_modules_path"] == str(node_modules.resolve())
    assert server_call.kwargs["is_server"] is True

    assert client_call.kwargs["paths"] == [[str(expected_view_path)]]
    assert client_call.kwargs["environment"] == "development"
    assert client_call.kwargs["live_reload_port"] == 123
    assert client_call.kwargs["node_modules_path"] == str(node_modules.resolve())
    assert client_call.kwargs["is_server"] is False


def test_bundler_production_environment(tmp_path: Path) -> None:
    view_root = tmp_path / "views"
    view_root.mkdir()
    node_modules = tmp_path / "node_modules"
    node_modules.mkdir()

    settings = Settings(
        view_root=view_root,
        node_modules_path=node_modules,
        PRODUCTION=True,
    )
    bundler = Bundler(settings=settings)

    with patch(
        "mountaineer.v2.bundler.mountaineer_rs.compile_independent_bundles"
    ) as mock_compile:
        mock_compile.side_effect = [
            (["server_js"], ["server_map"]),
            (["client_js"], ["client_map"]),
        ]

        bundler.compile(view_path=Path("page.tsx"))

    assert mock_compile.call_args_list[0].kwargs["environment"] == "production"
    assert mock_compile.call_args_list[1].kwargs["environment"] == "production"


def test_bundler_wraps_compile_error(tmp_path: Path) -> None:
    view_root = tmp_path / "views"
    view_root.mkdir()
    node_modules = tmp_path / "node_modules"
    node_modules.mkdir()

    settings = Settings(view_root=view_root, node_modules_path=node_modules)
    bundler = Bundler(settings=settings)

    with patch(
        "mountaineer.v2.bundler.mountaineer_rs.compile_independent_bundles",
        side_effect=ValueError("boom"),
    ):
        with raises(RuntimeError):
            bundler.compile(view_path=Path("page.tsx"))
