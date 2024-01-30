from contextlib import AsyncExitStack, asynccontextmanager
from functools import wraps
from inspect import Parameter, signature
from typing import Any, Callable, Type, overload
from urllib.parse import urlparse

from fastapi import Request
from fastapi.dependencies.utils import get_dependant, solve_dependencies
from pydantic import BaseModel
from starlette.routing import Match

from filzl.actions.fields import (
    FunctionActionType,
    get_function_metadata,
    init_function_metadata,
)
from filzl.controller import ControllerBase
from filzl.render import FieldClassDefinition


@overload
def sideeffect(
    # We need to typehint reload to be Any, because during typechecking our Model.attribute will just
    # yield whatever the typehint of that field is. Only at runtime does it become a FieldClassDefinition
    reload: tuple[Any, ...] | None = None,
    response_model: Type[BaseModel] | None = None,
) -> Callable[[Callable], Callable]:
    ...


@overload
def sideeffect(func: Callable) -> Callable:
    ...


def sideeffect(*args, **kwargs):
    """
    Mark a function as causing a sideeffect to the data. This will force a reload of the full (or partial) server state
    and sync these changes down to the client page.

    :reload: If provided, will ONLY reload these fields on the client side. By default will reload all fields. Otherwise, why
        specify a sideeffect at all? Note that even if this is provided, we will still regenerate a fully full state on the server
        as if render() is called again. This parameter only controls the data that is streamed back to the client in order to help
        reduce bandwidth of data that won't be changed.

    """

    def decorator_with_args(
        reload: tuple[FieldClassDefinition, ...] | None = None,
        response_model: Type[BaseModel] | None = None,
    ):
        def wrapper(func: Callable):
            original_sig = signature(func)
            function_needs_request = "request" in original_sig.parameters

            @wraps(func)
            async def inner(self: ControllerBase, *func_args, **func_kwargs):
                # Check if the original function expects a 'request' parameter
                request = func_kwargs.pop("request")
                if not request:
                    raise ValueError(
                        "Sideeffect function must have a 'request' parameter"
                    )

                if function_needs_request:
                    func_kwargs["request"] = request

                passthrough_values = func(self, *func_args, **func_kwargs)

                # We need to get the original function signature, and then call it with the request
                async with get_render_parameters(self, request) as values:
                    # Some render functions rely on the URL of the page to make different logic
                    # For this we rely on the Referrer header that is sent on the fetch(). Note that this
                    # referrer can be spoofed, so it assumes that the endpoint also internally validates
                    # the caller has correct permissions to access the data.
                    return dict(
                        sideeffect=self.render(**values),
                        passthrough=passthrough_values,
                    )

            # Update the signature of 'inner' to include 'request: Request'
            # We need to modify this to conform to the request parameters that are sniffed
            # when the component is mounted
            # https://github.com/tiangolo/fastapi/blob/a235d93002b925b0d2d7aa650b7ab6d7bb4b24dd/fastapi/dependencies/utils.py#L250
            sig = signature(inner)
            parameters = list(sig.parameters.values())
            if "request" not in sig.parameters:
                request_param = Parameter(
                    "request", Parameter.POSITIONAL_OR_KEYWORD, annotation=Request
                )
                parameters.insert(1, request_param)  # Insert after 'self'
            new_sig = sig.replace(parameters=parameters)
            inner.__wrapped__.__signature__ = new_sig  # type: ignore

            metadata = init_function_metadata(inner, FunctionActionType.SIDEEFFECT)
            metadata.reload_states = reload
            metadata.passthrough_model = response_model
            return inner

        return wrapper

    if args and callable(args[0]):
        # It's used as @sideeffect without arguments
        func = args[0]
        return decorator_with_args()(func)
    else:
        # It's used as @sideeffect(xyz=2) with arguments
        return decorator_with_args(*args, **kwargs)


@asynccontextmanager
async def get_render_parameters(
    controller: ControllerBase,
    request: Request,
):
    """
    render() components are allowed to have all of the same dependency injections
    that a normal endpoint does. This function parses the render function signature in
    the same way that FastAPI/Starlette do, so we're able to pretend as if a new request
    is coming into the view endpoint.

    NOTE: We exclude calls to background tasks, since these are rarely intended for
    automatic calls to the rendering due to side-effects.

    """
    # Synthetic request object as if we're coming from the original first page
    dependant = get_dependant(
        call=controller.render,
        path=controller.url,
    )

    # Create a synethic request object that we would use to access the core
    # html. This will be passed through the dependency resolution pipeline so to
    # render() it's indistinguishable from a real request and therefore will render
    # in the same way.
    # The referrer should capture the page that they're actually on
    referer = request.headers.get("referer")
    view_request = Request(
        {
            "type": request.scope["type"],
            "path": urlparse(referer or controller.url).path,
            "headers": request.headers.raw,
            "http_version": request.scope["http_version"],
            "method": "GET",
            "scheme": request.scope["scheme"],
            "client": request.scope["client"],
            "server": request.scope["server"],
        }
    )

    # Follow starlette's original logic to resolve routes, since this provides us the necessary
    # metadata about URL paths. Unlike in the general-purpose URL resolution case, however,
    # we already know which route should be resolved so we can shortcut having to
    # match non-relevant paths.
    # https://github.com/encode/starlette/blob/5c43dde0ec0917673bb280bcd7ab0c37b78061b7/starlette/routing.py#L544
    for route in get_function_metadata(controller.render).get_render_router().routes:
        match, child_scope = route.matches(view_request.scope)
        if match != Match.FULL:
            raise RuntimeError(
                f"Route {route} did not match ({match}) {view_request.scope}"
            )
        view_request.scope = {
            **view_request.scope,
            "path_params": {},
            "query_string": "",
            **child_scope,
        }

    async with AsyncExitStack() as async_exit_stack:
        values, errors, background_tasks, sub_response, _ = await solve_dependencies(
            request=view_request,
            dependant=dependant,
            async_exit_stack=async_exit_stack,
        )
        if background_tasks:
            raise RuntimeError(
                "Background tasks are not supported when calling a render() function, due to undesirable side-effects."
            )
        if errors:
            raise RuntimeError(
                f"Errors encountered while resolving dependencies for a render(): {controller} {errors}"
            )

        yield values