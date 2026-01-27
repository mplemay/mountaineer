from __future__ import annotations

import warnings
from typing import Any, Callable, Coroutine, ParamSpec, Type, TypeVar, overload

from pydantic import BaseModel

from mountaineer.actions.action_dec import action
from mountaineer.exceptions import APIException
from mountaineer.render import FieldClassDefinition

P = ParamSpec("P")
R = TypeVar("R")


@overload
def sideeffect(
    *,
    reload: tuple[FieldClassDefinition, ...] | None = None,
    response_model: Type[BaseModel] | None = None,  # Deprecated
    exception_models: list[Type[APIException]] | None = None,
    experimental_render_reload: bool | None = None,
) -> Callable[
    [Callable[P, R | Coroutine[Any, Any, R]]],
    Callable[..., Coroutine[Any, Any, Any]],
]: ...


@overload
def sideeffect(
    func: Callable[P, R | Coroutine[Any, Any, R]],
) -> Callable[..., Coroutine[Any, Any, Any]]: ...


def sideeffect(*args, **kwargs):  # type: ignore
    warnings.warn(
        "@sideeffect is deprecated. Use @page.action(update=...) instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    if kwargs.get("experimental_render_reload"):
        warnings.warn(
            "experimental_render_reload is not supported for @page.action.",
            DeprecationWarning,
            stacklevel=2,
        )

    update = kwargs.get("reload")
    if update is None:
        update = tuple()

    if args and callable(args[0]):
        func = args[0]
        return action(update=update)(func)

    return action(
        update=update,
        response_model=kwargs.get("response_model"),
        exception_models=kwargs.get("exception_models"),
        raw_response=kwargs.get("raw_response"),
    )
