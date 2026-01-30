from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from mountaineer.v2.page.core import Page
from mountaineer.v2.page.execution import resolve_action, resolve_data
from mountaineer.v2.page_renderer import build_page_html


@dataclass(slots=True, kw_only=True)
class CompiledPage:
    page: Page
    server_js: str
    client_js: str
    ssr_timeout: int

    def __call__(self, *, path: str) -> APIRouter:
        router = APIRouter(prefix=path if path != "/" else "")

        # Main SSR Route
        router.add_api_route(
            path="/" if path == "/" else "",
            endpoint=self.get,
            methods=["GET"],
            response_class=HTMLResponse,
        )

        # Data Endpoints
        for definition in self.page.data_definitions:
            if definition.expose:
                router.add_api_route(
                    path=f"/_data/{definition.name}",
                    endpoint=self._create_data_endpoint(definition.name),
                    methods=["GET"],
                    response_class=JSONResponse,
                )

        # Action Endpoints
        for name in self.page.action_definitions:
            router.add_api_route(
                path=f"/_action/{name}",
                endpoint=self._create_action_endpoint(name),
                methods=["POST"],
                response_class=JSONResponse,
            )

        return router

    async def get(self, request: Request) -> HTMLResponse:
        ssr_definitions = [d for d in self.page.data_definitions if d.ssr]

        initial_data = await resolve_data(
            definitions=ssr_definitions,
            request=request,
            path=request.url.path,
            params_model=self.page.params,
            overrides=None,
        )

        html = build_page_html(
            server_js=self.server_js,
            client_js=self.client_js,
            initial_data=initial_data,
            ssr_timeout=self.ssr_timeout,
        )
        return HTMLResponse(content=html)

    def _create_data_endpoint(self, name: str) -> Callable[[Request], Awaitable[JSONResponse]]:
        async def endpoint(request: Request) -> JSONResponse:
            return await self.data_endpoint(name=name, request=request)

        return endpoint

    def _create_action_endpoint(self, name: str) -> Callable[[Request], Awaitable[JSONResponse]]:
        async def endpoint(request: Request) -> JSONResponse:
            return await self.action_endpoint(name=name, request=request)

        return endpoint

    async def data_endpoint(self, *, name: str, request: Request) -> JSONResponse:
        definitions = [d for d in self.page.data_definitions if d.name == name]
        # Should be exactly one match if registered correctly

        data = await resolve_data(
            definitions=definitions,
            request=request,
            path=request.url.path,
            params_model=self.page.params,
            overrides=None,
        )
        return JSONResponse({"data": data})

    async def action_endpoint(self, *, name: str, request: Request) -> JSONResponse:
        definition = self.page.action_definitions[name]

        action_result = await resolve_action(
            definition=definition,
            request=request,
            path=request.url.path,
            params_model=self.page.params,
            overrides=None,
        )

        data_results: dict[str, Any] = {}
        if definition.update:
            update_defs = [d for d in self.page.data_definitions if d.name in definition.update]
            data_results = await resolve_data(
                definitions=update_defs,
                request=request,
                path=request.url.path,
                params_model=self.page.params,
                overrides=None,
            )

        return JSONResponse(
            {
                "action": action_result,
                "data": data_results,
            },
        )
