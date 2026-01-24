from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from mountaineer import Mountaineer
from mountaineer.development import session as session_module
from mountaineer.development.session import DevSession


def write_test_app(tmp_path: Path) -> str:
    package_name = f"test_app_{uuid4().hex}"
    package_dir = tmp_path / package_name
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("")

    views_dir = package_dir / "views"
    views_dir.mkdir()
    (views_dir / "test_controller").mkdir()
    (views_dir / "test_controller" / "page.tsx").write_text("")

    module_path = package_dir / "app.py"
    module_path.write_text(
        "from pathlib import Path\n"
        "from mountaineer import ControllerBase, Mountaineer\n"
        "\n"
        "class TestController(ControllerBase):\n"
        "    view_path = '/test_controller/page.tsx'\n"
        "    url = '/'\n"
        "\n"
        "    async def render(self) -> None:\n"
        "        return None\n"
        "\n"
        "mountaineer = Mountaineer(view_root=Path(__file__).parent / 'views')\n"
        "mountaineer.register(TestController())\n"
    )

    return f"{package_name}.app:mountaineer"


def test_from_webcontroller_initializes_app_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    webcontroller = write_test_app(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))

    session = DevSession.from_webcontroller(webcontroller=webcontroller)

    assert session.mountaineer is not None
    assert session.js_compiler is not None
    assert session.app_compiler is not None


@pytest.mark.asyncio
async def test_build_use_server_invokes_builder(tmp_path: Path):
    session = DevSession(
        webcontroller="package.module:mountaineer",
        package="package",
        module_name="package.module",
        controller_name="mountaineer",
        environment=None,
    )

    builder = SimpleNamespace(build_use_server=AsyncMock())
    session.js_compiler = builder  # type: ignore[assignment]

    await session.build_use_server()

    builder.build_use_server.assert_awaited_once()


@pytest.mark.asyncio
async def test_build_frontend_runs_plugins_and_invalidates(tmp_path: Path):
    session = DevSession(
        webcontroller="package.module:mountaineer",
        package="package",
        module_name="package.module",
        controller_name="mountaineer",
        environment=None,
    )

    session.mountaineer = Mountaineer(view_root=tmp_path)

    called = {}

    class DummyCompiler:
        async def run_builder_plugins(self, *, limit_paths: list[Path] | None = None):
            called["limit_paths"] = limit_paths

    session.app_compiler = DummyCompiler()  # type: ignore[assignment]

    invalidated: list[Path] = []

    def capture_invalidate(path: Path) -> None:
        invalidated.append(path)

    session.mountaineer.invalidate_view = capture_invalidate  # type: ignore[method-assign]

    changed_files = [tmp_path / "test.tsx", tmp_path / "nested" / "other.tsx"]
    await session.build_frontend(updated_js=changed_files)

    assert called["limit_paths"] == changed_files
    assert invalidated == changed_files


@pytest.mark.asyncio
async def test_start_and_stop_server(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    session = DevSession(
        webcontroller="package.module:mountaineer",
        package="package",
        module_name="package.module",
        controller_name="mountaineer",
        environment=None,
    )
    session.mountaineer = Mountaineer(view_root=tmp_path)

    class DummyThread:
        def __init__(
            self,
            *,
            name: str,
            emoticon: str,
            app,
            host: str,
            port: int,
        ):
            self.name = name
            self.emoticon = emoticon
            self.app = app
            self.host = host
            self.port = port
            self.started = False
            self.stopped = False
            self.joined = False

        async def astart(self) -> None:
            self.started = True

        async def astop(self) -> None:
            self.stopped = True

        def join(self, *, timeout: float | None = None) -> None:
            self.joined = True

    monkeypatch.setattr(session_module, "UvicornThread", DummyThread)

    await session.start_server(host="127.0.0.1", port=8000, live_reload_port=4321)

    assert session.mountaineer.live_reload_port == 4321
    assert session.webservice_thread is not None
    assert session.webservice_thread.started is True  # type: ignore[attr-defined]

    await session.stop_server()

    assert session.webservice_thread is None
