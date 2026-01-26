"""Type stubs for mountaineer._core Rust extension module."""

from typing import Any

class MapMetadata:
    """Source map location metadata."""

    line_number: int
    column_number: int
    source_index: int | None
    source_line: int | None
    source_column: int | None
    symbol_index: int | None

    def __init__(self, line_number: int, column_number: int) -> None: ...

class BuildContextParams:
    """Build context parameters for compilation."""

    path: str
    node_modules_path: str
    environment: str
    live_reload_port: int
    is_server: bool
    controller_name: str
    output_dir: str

    def __init__(
        self,
        path: str,
        node_modules_path: str,
        environment: str,
        live_reload_port: int,
        is_server: bool,
        controller_name: str,
        output_dir: str,
    ) -> None: ...

def render_ssr(js_string: str, hard_timeout: int) -> str:
    """Execute JS in V8 for server-side rendering.

    Raises:
        ConnectionAbortedError: If hard_timeout is reached
        ValueError: If V8 throws an exception
    """
    ...

def parse_source_map_mappings(mapping: str) -> dict[tuple[int, int], MapMetadata]:
    """Parse VLQ-encoded source map mappings."""
    ...

def compile_independent_bundles(
    paths: list[list[str]],
    node_modules_path: str,
    environment: str,
    live_reload_port: int,
    live_reload_import: str,
    is_server: bool,
    tsconfig_path: str | None = None,
) -> tuple[list[str], list[str]]:
    """Compile independent JS bundles for development."""
    ...

def compile_production_bundle(
    paths: list[list[str]],
    node_modules_path: str,
    environment: str,
    minify: bool,
    live_reload_import: str,
    is_server: bool,
    tsconfig_path: str | None = None,
) -> dict[str, Any]:
    """Compile production JS bundle with tree-shaking."""
    ...

def strip_js_comments(js_string: str) -> str:
    """Strip JavaScript comments from source code."""
    ...
