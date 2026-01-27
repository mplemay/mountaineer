from __future__ import annotations

import warnings
from typing import Any, Callable, Coroutine, ParamSpec, Type, TypeVar, overload

from pydantic import BaseModel

from mountaineer.actions.action_dec import action
from mountaineer.exceptions import APIException

P = ParamSpec("P")
R = TypeVar("R")


@overload
def passthrough(
    *,
    response_model: Type[BaseModel] | None = None,  # Deprecated
    exception_models: list[Type[APIException]] | None = None,
    raw_response: bool | None = None,
) -> Callable[
    [Callable[P, R | Coroutine[Any, Any, R]]],
    Callable[..., Coroutine[Any, Any, Any]],
]: ...


@overload
def passthrough(
    func: Callable[P, R | Coroutine[Any, Any, R]],
) -> Callable[..., Coroutine[Any, Any, Any]]: ...


def passthrough(*args, **kwargs):  # type: ignore
    warnings.warn(
        "@passthrough is deprecated. Use @page.action instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    if args and callable(args[0]):
        func = args[0]
        return action()(func)

    return action(
        update=None,
        response_model=kwargs.get("response_model"),
        exception_models=kwargs.get("exception_models"),
        raw_response=kwargs.get("raw_response"),
    )
