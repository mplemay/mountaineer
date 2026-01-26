import asyncio
import os
import signal
from os import environ
from pathlib import Path
from random import uniform
from shutil import copytree
from subprocess import Popen
from time import sleep, time

import httpx
import pytest
import toml

import mountaineer.cli as cli_module
from mountaineer import ControllerBase, Mountaineer
from mountaineer.cli import find_packages_with_prefix


@pytest.fixture
def tmp_example_webapp(tmp_path: Path):
    # Copy the full example package so we can make local modifications
    # just within this test
    raw_package = Path(__file__).parent.parent.parent / "example"
    mutable_package = tmp_path / "example"
    copytree(raw_package, mutable_package)

    pyproject_path = mutable_package / "pyproject.toml"
    base_package_path = Path(__file__).parent.parent.parent.resolve()

    with open(pyproject_path, "r") as file:
        content = toml.load(file)

    # Point to the absolute path of the local mountaineer core package, versus the
    # symlinked version in the original package. We only have one dependency so we can
    # just replace the entire bundle.
    assert len(content["project"]["dependencies"]) == 1
    content["project"]["dependencies"] = [
        f"mountaineer @ file://{str(base_package_path)}"
    ]

    with open(pyproject_path, "w") as file:
        toml.dump(content, file)

    return mutable_package


def test_find_packages_with_prefix():
    # Choose some packages that we know will be in the test environment
    assert set(find_packages_with_prefix("fasta")) == {"fastapi"}
    assert set(find_packages_with_prefix("pydan")) == {
        "pydantic",
        "pydantic_core",
        "pydantic-settings",
    }


@pytest.mark.asyncio
async def test_handle_build_uses_dev_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    views_dir = tmp_path / "views"
    views_dir.mkdir()

    class DummyController(ControllerBase):
        view_path = "/dummy_controller/page.tsx"
        url = "/"

        async def render(self) -> None:
            return None

    app = Mountaineer(view_root=views_dir)
    app.register(DummyController())

    class DummyCompiler:
        def __init__(self):
            self.called = False

        async def run_builder_plugins(self, *, limit_paths: list[Path] | None = None):
            self.called = True

    class DummySession:
        def __init__(self):
            self.mountaineer = app
            self.js_compiler = object()
            self.app_compiler = DummyCompiler()
            self.build_called = False

        async def build_use_server(self) -> None:
            self.build_called = True

    session = DummySession()

    monkeypatch.setattr(
        cli_module.DevSession,
        "from_webcontroller",
        lambda *, webcontroller: session,
    )

    def fake_compile_production_bundle(*_args, **_kwargs):
        return {
            "entrypoints": ["console.log('client');"],
            "entrypoint_maps": ["{}"],
            "supporting": {},
        }

    def fake_compile_independent_bundles(*_args, **_kwargs):
        return ["console.log('ssr');"], None

    monkeypatch.setattr(
        cli_module.mountaineer_rs,
        "compile_production_bundle",
        fake_compile_production_bundle,
    )
    monkeypatch.setattr(
        cli_module.mountaineer_rs,
        "compile_independent_bundles",
        fake_compile_independent_bundles,
    )

    handler = getattr(cli_module.handle_build, "__wrapped__", None)
    assert handler is not None
    await handler(
        webcontroller="package.module:mountaineer",
        minify=True,
    )

    assert session.build_called is True
    assert session.app_compiler.called is True
    assert (views_dir / "_static" / "dummy_controller.js").exists()
    assert (views_dir / "_ssr" / "dummy_controller.js").exists()


async def check_server_bound(port: int, timeout=8):
    # 5s hard timeout + 3s overhead
    # When the server restarting gets stuck it gets stuck permanently
    start_time = time()
    url = f"http://localhost:{port}"
    async with httpx.AsyncClient() as client:
        while time() - start_time < timeout:
            try:
                response = await client.get(url)
                return True, response.status_code
            except httpx.RequestError:
                pass
            await asyncio.sleep(0.1)
    return False, -1


@pytest.mark.integration_tests
@pytest.mark.asyncio
async def test_handle_runserver_with_user_modifications(tmp_example_webapp: Path):
    # Ensure that there is no existing webapp running
    port = 5006
    url = f"http://localhost:{port}"
    async with httpx.AsyncClient() as client:
        try:
            await client.get(url, timeout=1)
            assert False, "The server is already running"
        except httpx.RequestError:
            pass

    uv_env = {
        key: value
        for key, value in environ.items()
        if not key.startswith("VIRTUAL_ENV")
    }

    # We need to uv sync the packages at the new path
    return_code = Popen(["uv", "sync"], cwd=tmp_example_webapp, env=uv_env).wait()
    assert return_code == 0

    return_code = Popen(
        ["npm", "install"], cwd=tmp_example_webapp / "example" / "views", env=uv_env
    ).wait()
    assert return_code == 0

    # Start the handle_runserver function in a process
    server_process = Popen(
        ["uv", "run", "runserver", "--port", str(port)],
        cwd=tmp_example_webapp,
        env=uv_env,
    )
    test_file_path = tmp_example_webapp / "example" / "controllers" / "home.py"

    try:
        for _ in range(5):
            with open(test_file_path, "a") as f:
                print(f"Adding content to {test_file_path}")  # noqa: T201
                f.write("\npass\n")

            sleep(uniform(0.2, 2.0))

        # After all these random server restarts make sure that the
        # server is still running
        print(  # noqa: T201
            "Done with changes, checking that server will resolve if not immediately ready..."
        )
        is_bound, status_code = await check_server_bound(port)
        assert is_bound, "Server is not bound to localhost:3000"
        assert status_code == 200, "Server is not returning 200 status code"
        print("Server is bound to expected port")  # noqa: T201
    finally:
        # Terminate the processes after test
        os.kill(server_process.pid, signal.SIGKILL)
        server_process.wait()
