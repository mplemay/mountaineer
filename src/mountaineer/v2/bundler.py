from dataclasses import dataclass
from pathlib import Path

from mountaineer import _core as mountaineer_rs
from mountaineer.static import get_static_path
from mountaineer.v2.settings import Settings


@dataclass(slots=True, kw_only=True)
class BundleResult:
    client_js: str
    server_js: str


class Bundler:
    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings

    def compile(self, *, view_path: Path) -> BundleResult:
        resolved_view_path = view_path
        if not resolved_view_path.is_absolute():
            resolved_view_path = self._settings.view_root / view_path
        resolved_view_path = resolved_view_path.resolve()

        paths = [[str(resolved_view_path)]]
        node_modules_path = str(self._settings.node_modules_path.resolve())
        environment = self._settings.environment
        live_reload_import = str(get_static_path("live_reload.ts").resolve())

        try:
            server_scripts, _ = mountaineer_rs.compile_independent_bundles(
                paths=paths,
                node_modules_path=node_modules_path,
                environment=environment,
                live_reload_port=self._settings.live_reload_port,
                live_reload_import=live_reload_import,
                is_server=True,
            )
            client_scripts, _ = mountaineer_rs.compile_independent_bundles(
                paths=paths,
                node_modules_path=node_modules_path,
                environment=environment,
                live_reload_port=self._settings.live_reload_port,
                live_reload_import=live_reload_import,
                is_server=False,
            )
        except Exception as exc:
            msg = f"Failed to compile view at {resolved_view_path}"
            raise RuntimeError(msg) from exc

        return BundleResult(
            client_js=client_scripts[0],
            server_js=server_scripts[0],
        )
