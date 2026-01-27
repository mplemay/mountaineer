from pathlib import Path

import pytest
from fastapi import Depends
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from starlette.requests import Request

from mountaineer import Metadata, Page
from mountaineer.render import RenderBase
from mountaineer.render_resolver import RenderResolver


class ExampleParams(BaseModel):
    item_id: int
    query: str | None = None


def _make_request(path: str, *, query: str = "", path_params: dict | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "path": path,
            "path_params": path_params or {},
            "query_string": query.encode(),
            "headers": [],
        }
    )


@pytest.mark.asyncio
async def test_resolve_full_and_partial():
    page = Page(view=Path("page.tsx"), path="/items/{item_id}", params=ExampleParams)

    @page.data(name="item_id")
    def get_item_id(params: ExampleParams) -> int:
        return params.item_id

    @page.data(name="query")
    def get_query(params: ExampleParams) -> str | None:
        return params.query

    controller = page.build()
    request = _make_request("/items/5", query="query=hello", path_params={"item_id": 5})

    full = await RenderResolver.resolve(
        controller=controller,
        request=request,
        metadata_loader=None,
    )
    assert isinstance(full, RenderBase)
    assert full.item_id == 5
    assert full.query == "hello"

    partial = await RenderResolver.resolve(
        controller=controller,
        request=request,
        loaders=["item_id"],
        metadata_loader=None,
    )
    assert partial == {"item_id": 5}


@pytest.mark.asyncio
async def test_resolve_dependencies_and_metadata():
    page = Page(view=Path("page.tsx"), path="/items/{item_id}", params=ExampleParams)

    def get_value() -> int:
        return 7

    @page.data(name="dep_value")
    def get_dep_value(value: int = Depends(get_value)) -> int:
        return value

    @page.metadata
    def get_metadata(params: ExampleParams) -> Metadata:
        return Metadata(title=f"Item {params.item_id}")

    controller = page.build()
    request = _make_request("/items/3", path_params={"item_id": 3})

    result = await RenderResolver.resolve(
        controller=controller,
        request=request,
        metadata_loader=getattr(controller, "_page_metadata_loader", None),
    )

    assert isinstance(result, RenderBase)
    assert result.dep_value == 7
    assert result.metadata
    assert result.metadata.title == "Item 3"


@pytest.mark.asyncio
async def test_resolve_json_response_loader():
    page = Page(view=Path("page.tsx"), path="/")

    @page.data(name="payload")
    def get_payload() -> JSONResponse:
        return JSONResponse(content={"value": 5})

    controller = page.build()
    result = await RenderResolver.resolve(
        controller=controller,
        request=_make_request("/"),
        metadata_loader=None,
    )

    assert isinstance(result, RenderBase)
    assert result.payload == {"value": 5}


@pytest.mark.asyncio
async def test_resolve_invalid_response_type():
    page = Page(view=Path("page.tsx"), path="/")

    @page.data(name="payload")
    def get_payload() -> Response:
        return Response(content="nope")

    controller = page.build()
    with pytest.raises(ValueError, match="Only JSONResponse is supported"):
        await RenderResolver.resolve(
            controller=controller,
            request=_make_request("/"),
            metadata_loader=None,
        )
