from pathlib import Path

from pydantic import BaseModel

from mountaineer import Page


class RootLayoutParams(BaseModel):
    layout_arg: int | None = None


page = Page(view=Path("app/layout.tsx"), layout=True, params=RootLayoutParams)

_layout_value = 0


@page.data(ssr=True, name="layout_value")
async def get_layout_value() -> int:
    return _layout_value


@page.data(ssr=True, name="layout_arg")
async def get_layout_arg(params: RootLayoutParams) -> int:
    return params.layout_arg or 0


@page.action(update=(get_layout_value,))
async def increment_layout_value() -> None:
    global _layout_value
    _layout_value += 1
