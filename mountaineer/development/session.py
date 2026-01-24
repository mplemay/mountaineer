import importlib
from pathlib import Path
from tempfile import mkdtemp
from typing import Self

from firehot.environment import Environment

from mountaineer.app import Mountaineer
from mountaineer.client_builder.builder import APIBuilder
from mountaineer.client_compiler.compile import ClientCompiler
from mountaineer.development.reload import ModuleReloader
from mountaineer.development.uvicorn import UvicornThread


class DevSession:
    def __init__(
        self,
        *,
        webcontroller: str,
        package: str,
        module_name: str,
        controller_name: str,
        environment: Environment | None,
    ):
        self.webcontroller = webcontroller
        self.package = package
        self.module_name = module_name
        self.controller_name = controller_name
        self.environment = environment

        self.mountaineer: Mountaineer | None = None
        self.js_compiler: APIBuilder | None = None
        self.app_compiler: ClientCompiler | None = None
        self.reloader = ModuleReloader(package=package)
        self.webservice_thread: UvicornThread | None = None
        self.module = None

    @classmethod
    def from_webcontroller(
        cls, *, webcontroller: str, environment: Environment | None = None
    ) -> Self:
        package, module_name, controller_name = cls._parse_webcontroller(webcontroller)
        session = cls(
            webcontroller=webcontroller,
            package=package,
            module_name=module_name,
            controller_name=controller_name,
            environment=environment,
        )
        session.initialize_app_state()
        return session

    @staticmethod
    def _parse_webcontroller(webcontroller: str) -> tuple[str, str, str]:
        if ":" not in webcontroller:
            raise ValueError(
                f"Invalid webcontroller format: {webcontroller}. Expected 'module:var'."
            )
        module_name, controller_name = webcontroller.split(":", maxsplit=1)
        if "." not in module_name:
            raise ValueError(
                f"Invalid webcontroller format: {webcontroller}. Expected package.module."
            )
        package = module_name.split(".", maxsplit=1)[0]
        return package, module_name, controller_name

    def initialize_app_state(self) -> None:
        self.module = importlib.import_module(name=self.module_name)
        mountaineer = getattr(self.module, self.controller_name, None)
        if not isinstance(mountaineer, Mountaineer):
            raise ValueError("App controller not initialized")

        self.mountaineer = mountaineer

        global_build_cache = Path(mkdtemp())
        self.js_compiler = APIBuilder(
            self.mountaineer,
            build_cache=global_build_cache,
        )
        self.app_compiler = ClientCompiler(app=self.mountaineer)

    async def build_use_server(self) -> None:
        if self.js_compiler is None:
            raise ValueError("JS compiler not initialized")
        await self.js_compiler.build_use_server()

    async def build_frontend(self, updated_js: list[Path] | None) -> None:
        if self.app_compiler is None:
            raise ValueError("App compiler not initialized")
        if self.mountaineer is None:
            raise ValueError("App controller not initialized")

        await self.app_compiler.run_builder_plugins(limit_paths=updated_js)
        for path in updated_js or []:
            self.mountaineer.invalidate_view(path)

    async def start_server(
        self, *, host: str, port: int, live_reload_port: int
    ) -> None:
        if self.webservice_thread is not None:
            return
        if self.mountaineer is None:
            raise ValueError("App controller not initialized")

        self.mountaineer.live_reload_port = live_reload_port or 0
        self.webservice_thread = UvicornThread(
            name="Dev webserver",
            emoticon="🚀",
            app=self.mountaineer.app,
            host=host,
            port=port,
        )
        await self.webservice_thread.astart()

    async def stop_server(self) -> None:
        if self.webservice_thread is None:
            return
        await self.webservice_thread.astop()
        self.webservice_thread.join(timeout=1)
        self.webservice_thread = None

    async def restart_server(
        self, *, host: str, port: int, live_reload_port: int
    ) -> None:
        await self.stop_server()
        await self.start_server(host=host, port=port, live_reload_port=live_reload_port)

    def reload_python(self, *, changed_files: list[Path]) -> bool:
        if self.environment is not None:
            self.environment.update_environment()

        if not changed_files:
            return True

        modules = self.reloader.modules_from_paths(changed_files)
        if not modules:
            return True

        if not self.reloader.reload_modules(modules):
            return False

        try:
            self.initialize_app_state()
        except Exception:
            return False

        return True
