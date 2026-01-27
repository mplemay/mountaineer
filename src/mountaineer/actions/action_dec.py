from __future__ import annotations

from functools import wraps
from inspect import isasyncgen, isasyncgenfunction, isawaitable, isgeneratorfunction
from json import dumps as json_dumps
from typing import Any, AsyncIterator, Callable, Coroutine, Literal, ParamSpec, Type, TypeVar, overload

from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel

from mountaineer.actions.fields import (
    FunctionActionType,
    ResponseModelType,
    create_original_fn,
    extract_response_model_from_signature,
    format_final_action_response,
    init_function_metadata,
)
from mountaineer.constants import STREAM_EVENT_TYPE
from mountaineer.exceptions import APIException
from mountaineer.render import FieldClassDefinition

P = ParamSpec("P")
R = TypeVar("R", bound=BaseModel | AsyncIterator[BaseModel] | JSONResponse | None)

RawResponseR = TypeVar("RawResponseR", bound=Response)


@overload
def action(
    *,
    update: tuple[FieldClassDefinition, ...] | None = None,
    response_model: Type[BaseModel] | None = None,
    exception_models: list[Type[APIException]] | None = None,
    raw_response: Literal[False] | None = None,
) -> Callable[
    [Callable[P, R | Coroutine[Any, Any, R]]],
    Callable[..., Coroutine[Any, Any, Any]],
]: ...


@overload
def action(
    *,
    update: tuple[FieldClassDefinition, ...] | None = None,
    raw_response: Literal[True] = True,
) -> Callable[
    [Callable[P, RawResponseR | Coroutine[Any, Any, RawResponseR]]],
    Callable[..., Coroutine[Any, Any, Any]],
]: ...


@overload
def action(
    func: Callable[P, R | Coroutine[Any, Any, R]],
) -> Callable[..., Coroutine[Any, Any, Any]]: ...


def action(*args, **kwargs):  # type: ignore
    def decorator_with_args(
        update: tuple[FieldClassDefinition, ...] | None = None,
        response_model: Type[BaseModel] | None = None,
        exception_models: list[Type[APIException]] | None = None,
        raw_response: bool | None = None,
    ):
        def wrapper(func: Callable):
            passthrough_model, response_type = extract_response_model_from_signature(
                func, response_model
            )

            if response_type == ResponseModelType.ITERATOR_RESPONSE and update:
                raise ValueError(
                    "Streaming responses are not supported for update actions"
                )

            if raw_response and update:
                raise ValueError("raw_response is not supported for update actions")

            if isgeneratorfunction(func):
                raise ValueError(
                    f"Only async generators are supported: Define {func} as `async def`"
                )

            if (
                isasyncgenfunction(func)
                and response_type != ResponseModelType.ITERATOR_RESPONSE
            ):
                raise ValueError(
                    f"Async generator {func} must have a response_model of type AsyncIterator[BaseModel]"
                )

            @wraps(func)
            async def inner(self: Any, *func_args, **func_kwargs):
                response = func(self, *func_args, **func_kwargs)
                if isawaitable(response):
                    response = await response

                if raw_response:
                    return response

                if isasyncgen(response):
                    return wrap_passthrough_generator(response)

                final_payload: dict[str, Any] = {
                    "passthrough": response,
                }

                if update is not None:
                    reload_states = get_reload_names(metadata.reload_states)
                    final_payload["reload"] = reload_states

                return format_final_action_response(final_payload)

            metadata = init_function_metadata(
                inner,
                FunctionActionType.SIDEEFFECT if update is not None else FunctionActionType.PASSTHROUGH,
            )
            metadata.reload_states = update
            metadata.passthrough_model = passthrough_model
            metadata.exception_models += exception_models or []
            metadata.is_raw_response = raw_response or False
            metadata.media_type = (
                STREAM_EVENT_TYPE
                if response_type == ResponseModelType.ITERATOR_RESPONSE
                else None
            )
            metadata.reload_action = update is not None

            inner.original = create_original_fn(func)  # type: ignore
            return inner

        return wrapper

    if args and callable(args[0]):
        func = args[0]
        return decorator_with_args()(func)
    else:
        return decorator_with_args(
            update=kwargs.get("update"),
            response_model=kwargs.get("response_model"),
            exception_models=kwargs.get("exception_models"),
            raw_response=kwargs.get("raw_response"),
        )


def wrap_passthrough_generator(generator: AsyncIterator[BaseModel]):
    async def generate():
        async for value in generator:
            json_payload = value.model_dump(mode="json")
            data = json_dumps(dict(passthrough=json_payload))
            yield f"data: {data}\n"

    return StreamingResponse(generate(), media_type=STREAM_EVENT_TYPE)


def get_reload_names(reload_states: Any) -> list[str]:
    if reload_states is None:
        return []

    if isinstance(reload_states, (list, tuple)):
        names: list[str] = []
        for item in reload_states:
            if hasattr(item, "key"):
                names.append(item.key)
            elif isinstance(item, str):
                names.append(item)
            elif callable(item):
                names.append(item.__name__)
            else:
                raise ValueError(f"Unsupported reload state: {item}")
        return names

    if hasattr(reload_states, "key"):
        return [reload_states.key]

    if isinstance(reload_states, str):
        return [reload_states]

    raise ValueError(f"Unsupported reload state: {reload_states}")
