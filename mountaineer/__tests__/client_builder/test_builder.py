from dataclasses import asdict
from json import dumps as json_dumps
from json import loads as json_loads
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from mountaineer.app import AppController
from mountaineer.client_builder.builder import ClientBuilder
from mountaineer.controller import ControllerBase


class ExampleHomeController(ControllerBase):
    url = "/"
    view_path = "/page.tsx"

    def render(self) -> None:
        return None


class ExampleDetailController(ControllerBase):
    url = "/detail/{detail_id}/"
    view_path = "/detail/page.tsx"

    def render(self) -> None:
        return None


@pytest.fixture
def home_controller():
    return ExampleHomeController()


@pytest.fixture
def detail_controller():
    return ExampleDetailController()


@pytest.fixture(scope="function")
def simple_app_controller(
    home_controller: ExampleHomeController, detail_controller: ExampleDetailController
):
    with TemporaryDirectory() as temp_dir_name:
        temp_view_path = Path(temp_dir_name)
        (temp_view_path / "detail").mkdir()

        # Simple view files
        (temp_view_path / "page.tsx").write_text("")
        (temp_view_path / "detail" / "page.tsx").write_text("")

        app_controller = AppController(view_root=temp_view_path)
        app_controller.register(home_controller)
        app_controller.register(detail_controller)
        yield app_controller


@pytest.fixture
def builder(simple_app_controller: AppController):
    return ClientBuilder(simple_app_controller)


def test_generate_static_files(builder: ClientBuilder):
    builder.generate_static_files()


def test_generate_model_definitions(builder: ClientBuilder):
    builder.generate_model_definitions()


def test_generate_action_definitions(builder: ClientBuilder):
    builder.generate_action_definitions()


def test_generate_view_definitions(builder: ClientBuilder):
    builder.generate_link_shortcuts()


def test_generate_link_aggregator(builder: ClientBuilder):
    builder.generate_link_aggregator()


def test_generate_view_servers(builder: ClientBuilder):
    builder.generate_view_servers()


def test_generate_index_file(builder: ClientBuilder):
    builder.generate_index_file()


def test_cache_is_outdated_no_cache(builder: ClientBuilder):
    # No cache
    builder.build_cache = None
    assert builder.cache_is_outdated() is True


def test_cache_is_outdated_no_existing_data(builder: ClientBuilder, tmp_path: Path):
    builder.build_cache = tmp_path

    assert builder.cache_is_outdated() is True

    # Ensure that we've written to the cache
    cache_path = tmp_path / "client_builder_openapi.json"
    assert cache_path.exists()
    assert set(json_loads(cache_path.read_text()).keys()) == {
        "ExampleHomeController",
        "ExampleDetailController",
    }


def test_cache_is_outdated_existing_data(
    builder: ClientBuilder,
    tmp_path: Path,
    home_controller: ExampleHomeController,
    detail_controller: ExampleDetailController,
):
    builder.build_cache = tmp_path

    # Ensure that we've written to the cache
    cache_path = tmp_path / "client_builder_openapi.json"
    cache_path.write_text(
        json_dumps(
            {
                "ExampleHomeController": {
                    "action": builder.openapi_action_specs[home_controller],
                    "render": asdict(builder.openapi_render_specs[home_controller]),
                },
                "ExampleDetailController": {
                    "action": builder.openapi_action_specs[detail_controller],
                    "render": asdict(builder.openapi_render_specs[detail_controller]),
                },
            },
            sort_keys=True,
        )
    )

    assert builder.cache_is_outdated() is False
