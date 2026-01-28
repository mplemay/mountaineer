from collections.abc import Awaitable, Callable
from inspect import signature
from typing import Any

from fastapi import Depends, Request
from pydantic import BaseModel

from mountaineer.dependencies import get_function_dependencies
from mountaineer.v2.page.action import ActionDefinition
from mountaineer.v2.page.data import DataDefinition


def _get_params_dependency(params_model: type[BaseModel]) -> Callable[[Request], Any]:
    async def dependency(request: Request) -> BaseModel:
        # Merge path params and query params
        # Path params take precedence? Or Query?
        # Usually path params are more specific.
        values = {}
        values.update(request.query_params)
        values.update(request.path_params)
        return params_model(**values)

    return dependency


async def resolve_call(
    *,
    handler: Callable[..., Awaitable[Any]],
    request: Request,
    path: str,
    params_model: type[BaseModel] | None = None,
    dependency_overrides: dict[Callable, Callable] | None = None,
) -> Any:
    target_handler = handler

    if params_model:
        sig = signature(handler)
        params = list(sig.parameters.values())

        if params:
            p0 = params[0]
            if p0.default == p0.empty:
                # Use our custom dependency that pulls from path_params + query_params
                new_p0 = p0.replace(default=Depends(_get_params_dependency(params_model)))
                new_params = [new_p0] + params[1:]
                new_sig = sig.replace(parameters=new_params)

                async def wrapper(*args: Any, **kwargs: Any) -> Any:
                    pass

                wrapper.__signature__ = new_sig  # type: ignore
                wrapper.__name__ = handler.__name__
                target_handler = wrapper

    async with get_function_dependencies(
        callable=target_handler,
        url=path,
        request=request,
        dependency_overrides=dependency_overrides,
    ) as resolved_values:
        return await handler(**resolved_values)


async def resolve_data(
    *,
    definitions: list[DataDefinition[object]],
    request: Request,
    path: str,
    params_model: type[BaseModel] | None,
    overrides: dict[Callable, Callable] | None,
) -> dict[str, object]:
    results = {}
    for definition in definitions:
        results[definition.name] = await resolve_call(
            handler=definition.handler,
            request=request,
            path=path,
            params_model=params_model,
            dependency_overrides=overrides,
        )
    return results


async def resolve_action(
    *,
    definition: ActionDefinition,
    request: Request,
    path: str,
    params_model: type[BaseModel] | None,
    overrides: dict[Callable, Callable] | None,
) -> object:
    return await resolve_call(
        handler=definition.handler,
        request=request,
        path=path,
        params_model=params_model,
        dependency_overrides=overrides,
    )
