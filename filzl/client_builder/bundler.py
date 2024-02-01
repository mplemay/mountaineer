import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import BaseModel

from filzl.client_builder.esbuild import ESBuildWrapper
from filzl.client_interface.paths import generate_relative_import


class BundleOutput(BaseModel):
    client_compiled_contents: str
    client_source_map_contents: str
    server_compiled_contents: str
    server_source_map_contents: str


class JavascriptBundler:
    """
    Compile the client-written tsx/jsx to raw javascript files for execution as part
    of the SSR pipeline and client hydration.
    """

    def __init__(
        self, page_path: Path, view_root_path: Path, root_element: str = "root"
    ):
        self.page_path = page_path
        self.view_root_path = view_root_path
        self.root_element = root_element

    async def convert(self):
        # Before starting, make sure all the files are valid
        self.validate_page(self.page_path, self.view_root_path)

        layout_paths = self.sniff_for_layouts()

        # esbuild works on disk files
        with TemporaryDirectory() as temp_dir_name:
            temp_dir_path = Path(temp_dir_name)

            # The same endpoint definition is used for both SSR and the client build
            synthetic_payload = self.build_synthetic_endpoint(
                layout_paths, temp_dir_path / "dist"
            )

            client_entrypoint = self.build_synthetic_client_page(*synthetic_payload)
            ssr_entrypoint = self.build_synthetic_ssr_page(*synthetic_payload)

            self.link_project_files(temp_dir_path)
            (temp_dir_path / "synthetic_client.tsx").write_text(client_entrypoint)
            (temp_dir_path / "synthetic_server.tsx").write_text(ssr_entrypoint)

            common_loader = {
                ".tsx": "tsx",
                ".jsx": "jsx",
            }

            es_builder = ESBuildWrapper()
            await asyncio.gather(
                *[
                    es_builder.bundle(
                        entry_points=[temp_dir_path / "synthetic_client.tsx"],
                        outfile=temp_dir_path / "dist" / "synthetic_client.js",
                        output_format="esm",
                        bundle=True,
                        sourcemap=True,
                        loaders=common_loader,
                    ),
                    es_builder.bundle(
                        entry_points=[temp_dir_path / "synthetic_server.tsx"],
                        outfile=temp_dir_path / "dist" / "synthetic_server.js",
                        output_format="iife",
                        global_name="SSR",
                        define={
                            "global": "window",
                        },
                        bundle=True,
                        sourcemap=True,
                        loaders=common_loader,
                    ),
                ]
            )

            # Read these files
            return BundleOutput(
                client_compiled_contents=(
                    temp_dir_path / "dist" / "synthetic_client.js"
                ).read_text(),
                client_source_map_contents=(
                    temp_dir_path / "dist" / "synthetic_client.js.map"
                ).read_text(),
                server_compiled_contents=(
                    temp_dir_path / "dist" / "synthetic_server.js"
                ).read_text(),
                server_source_map_contents=(
                    temp_dir_path / "dist" / "synthetic_server.js.map"
                ).read_text(),
            )

    def build_synthetic_client_page(
        self,
        synthetic_imports: list[str],
        synthetic_endpoint: str,
        synthetic_endpoint_name: str,
    ):
        lines: list[str] = []

        # Assume the client page is always being called from a page that has been
        # initially rendered by SSR
        lines.append("import * as React from 'react';")
        lines.append("import { hydrateRoot } from 'react-dom/client';")
        lines += synthetic_imports

        lines.append(synthetic_endpoint)

        lines.append(
            f"const container = document.getElementById('{self.root_element}');"
        )
        lines.append(f"hydrateRoot(container, <{synthetic_endpoint_name} />);")

        return "\n".join(lines)

    def build_synthetic_ssr_page(
        self,
        synthetic_imports: list[str],
        synthetic_endpoint: str,
        synthetic_endpoint_name: str,
    ):
        lines: list[str] = []

        lines.append("import * as React from 'react';")
        lines.append("import { renderToString } from 'react-dom/server';")
        lines += synthetic_imports

        lines.append(synthetic_endpoint)

        lines.append(
            f"export const Index = () => renderToString(<{synthetic_endpoint_name} />);"
        )

        return "\n".join(lines)

    def link_project_files(self, temp_dir_path: Path):
        """
        Javascript packages define a variety of build metadata in the root directory
        of the project (tsconfig.json, package.json, etc). Since we're running our esbuild pipeline
        in a temporary directory, we need to copy over the key files. We use a symbolic link
        to avoid copying the files over.
        """
        to_link = ["package.json", "tsconfig.json", "node_modules"]

        for file_name in to_link:
            (temp_dir_path / file_name).symlink_to(self.view_root_path / file_name)

    def build_synthetic_endpoint(self, layout_paths: list[Path], output_path: Path):
        """
        Following the Next.js syntax, layouts wrap individual pages in a top-down order. Here we
        create a synthetic page that wraps the actual page in the correct order.
        The output is a valid React file that acts as the page entrypoint
        for the `rootElement` ID in the DOM.

        """
        # All import paths have to be a relative path from the scratch directory
        # to the original file
        import_paths: list[str] = []

        import_paths.append(
            f"import Page from '{generate_relative_import(output_path, self.page_path)}';"
        )

        for i, layout_path in enumerate(layout_paths):
            import_paths.append(
                f"import Layout{i} from '{generate_relative_import(output_path, layout_path)}';"
            )

        # The synthetic endpoint is a function that returns a React component
        entrypoint_name = "Entrypoint"
        content_lines = [
            f"const {entrypoint_name} = () => {{",
            "return (",
            *[f"<Layout{i}>" for i in range(len(layout_paths))],
            "<Page />",
            *[f"</Layout{i}>" for i in reversed(range(len(layout_paths)))],
            ");",
            "};",
        ]

        return import_paths, "\n".join(content_lines), entrypoint_name

    def sniff_for_layouts(self):
        """
        Given a page.tsx path, find all the layouts that apply to it.
        Returns the layout paths that are found. Orders them from the top->down
        as they expect to be rendered.

        """
        # It's easier to handle absolute paths when doing direct string comparisons
        # of the file hierarchy.
        page_path = self.page_path.resolve().absolute()
        view_root_path = self.view_root_path.resolve().absolute()

        # Starting at the page path, walk up the directory tree and yield each layout
        # that is found.
        layouts: list[Path] = []
        current_path = page_path.parent

        while current_path != view_root_path:
            layout_path_tsx = current_path / "layout.tsx"
            layout_path_jsx = current_path / "layout.jsx"

            # We shouldn't have both in the same directory
            if layout_path_tsx.exists() and layout_path_jsx.exists():
                raise ValueError(
                    f"Duplicate layout definitions: {layout_path_tsx}, {layout_path_jsx}"
                )

            if layout_path_tsx.exists():
                layouts.append(layout_path_tsx)
            if layout_path_jsx.exists():
                layouts.append(layout_path_jsx)

            current_path = current_path.parent

        # Return the layouts in the order they should be rendered
        return list(reversed(layouts))

    def validate_page(self, page_path: Path, view_root_path: Path):
        # Validate that we're actually calling on a path file
        if page_path.name not in {"page.tsx", "page.jsx"}:
            raise ValueError(f"Invalid page path: {page_path}")

        # Validate that the page_path is within the view root. The following
        # logic assumes a hierarchical relationship between the two.
        if not page_path.is_relative_to(view_root_path):
            raise ValueError(f"Invalid page path: {page_path}")
