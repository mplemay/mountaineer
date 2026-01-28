import pytest
from fastapi import Depends, Request
from pydantic import BaseModel

from mountaineer.v2.page.action import ActionDefinition
from mountaineer.v2.page.data import DataDefinition
from mountaineer.v2.page.execution import resolve_action, resolve_call, resolve_data


class PostParams(BaseModel):
    slug: str


async def get_value() -> int:
    return 10


async def get_value_override() -> int:
    return 99


@pytest.mark.asyncio
async def test_resolve_call_simple_dependencies() -> None:
    async def handler(val: int = Depends(get_value)) -> int:
        return val

    request = Request(scope={"type": "http", "path": "/", "query_string": b"", "headers": []})

    result = await resolve_call(
        handler=handler,
        request=request,
        path="/",
    )
    assert result == 10


@pytest.mark.asyncio
async def test_resolve_call_with_overrides() -> None:
    async def handler(val: int = Depends(get_value)) -> int:
        return val

    request = Request(scope={"type": "http", "path": "/", "query_string": b"", "headers": []})

    result = await resolve_call(
        handler=handler,
        request=request,
        path="/",
        dependency_overrides={get_value: get_value_override},
    )
    assert result == 99


@pytest.mark.asyncio
async def test_resolve_call_with_params_model() -> None:
    # Handler expects params: PostParams.
    # We simulate a request where slug comes from path params (simulated by URL matching).

    async def handler(params: PostParams) -> str:
        return params.slug

    request = Request(
        scope={
            "type": "http",
            "path": "/post/my-slug",
            "path_params": {"slug": "my-slug"},  # FastAPI router usually populates this
            "query_string": b"",
            "headers": [],
        }
    )

    result = await resolve_call(
        handler=handler,
        request=request,
        path="/post/my-slug",
        params_model=PostParams,
    )
    assert result == "my-slug"


@pytest.mark.asyncio
async def test_resolve_data_multiple() -> None:
    async def handler1() -> int:
        return 1

    async def handler2() -> int:
        return 2

    defs = [
        DataDefinition(name="h1", handler=handler1, ssr=True, expose=True),
        DataDefinition(name="h2", handler=handler2, ssr=True, expose=True),
    ]

    request = Request(scope={"type": "http", "path": "/", "query_string": b"", "headers": []})

    results = await resolve_data(
        definitions=defs,
        request=request,
        path="/",
        params_model=None,
        overrides=None,
    )

    assert results == {"h1": 1, "h2": 2}


@pytest.mark.asyncio
async def test_resolve_action_execution() -> None:
    async def action_handler() -> str:
        return "done"

    definition = ActionDefinition(name="act", handler=action_handler, update=None)

    request = Request(scope={"type": "http", "path": "/", "query_string": b"", "headers": []})

    result = await resolve_action(
        definition=definition,
        request=request,
        path="/",
        params_model=None,
        overrides=None,
    )
    assert result == "done"
