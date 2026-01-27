from dataclasses import dataclass

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from mountaineer.v2.html import build_page_html
from mountaineer.v2.page.core import Page


@dataclass(slots=True, kw_only=True)
class CompiledPage:
    page: Page
    server_js: str
    client_js: str
    ssr_timeout: int

    def __call__(self) -> APIRouter:
        router = APIRouter()
        router.add_api_route(
            path="",
            endpoint=self.get,
            methods=["GET"],
            response_class=HTMLResponse,
        )
        return router

    async def get(self) -> HTMLResponse:
        html = build_page_html(
            server_js=self.server_js,
            client_js=self.client_js,
            initial_data={},
            ssr_timeout=self.ssr_timeout,
        )
        return HTMLResponse(content=html)
