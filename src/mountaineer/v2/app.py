from fastapi import FastAPI
from starlette.types import Receive, Scope, Send

from mountaineer.v2.bundler import Bundler
from mountaineer.v2.page.core import Page
from mountaineer.v2.settings import Settings


class Mountaineer:
    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings
        self._app = FastAPI()
        self._bundler = Bundler(settings=settings)
        self._registered_paths: set[str] = set()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self._app(scope=scope, receive=receive, send=send)

    def include_page(self, *, page: Page) -> None:
        if page.path in self._registered_paths:
            raise ValueError(f"Page path already registered: {page.path}")

        bundle = self._bundler.compile(view_path=page.view)
        compiled_page = page(
            server_js=bundle.server_js,
            client_js=bundle.client_js,
            ssr_timeout=self._settings.ssr_timeout,
        )
        self._app.include_router(router=compiled_page(path=page.path))
        self._registered_paths.add(page.path)
