from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, TypeVar

from pydantic import BaseModel

from mountaineer.v2.page.action import ActionDefinition
from mountaineer.v2.page.data import DataDefinition

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

    from mountaineer.v2.page.compiled import CompiledPage


class NamedCallable(Protocol):
    __name__: str

    def __call__(self, *args: object, **kwargs: object) -> Awaitable[object]: ...


F = TypeVar("F", bound=NamedCallable)


@dataclass(slots=True, kw_only=True)
class Page:
    view: Path
    path: str
    params: type[BaseModel] | None = None
    _data: list[DataDefinition[object]] = field(default_factory=list)
    _actions: dict[str, ActionDefinition] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.path.startswith("/"):
            msg = "Page path must start with '/'"
            raise ValueError(msg)

        trimmed = self.path[1:]
        # Allow root path "/" which results in empty string after slice
        if self.path != "/":
            segments = trimmed.split("/")
            if any(segment == "" for segment in segments):
                msg = "Page path must not contain empty segments"
                raise ValueError(msg)

            # Check for dynamic segments
            dynamic_segments = [seg for seg in segments if seg.startswith("{") and seg.endswith("}")]

            if dynamic_segments:
                if len(dynamic_segments) > 1:
                    msg = f"Only one dynamic path segment is allowed. Found: {dynamic_segments}"
                    raise ValueError(msg)

                param_name = dynamic_segments[0][1:-1]
                if param_name != "slug":
                    msg = f"Dynamic path segment must be named '{{slug}}'. Found: '{{{param_name}}}'"
                    raise ValueError(msg)

                if self.params is None:
                    msg = "Page path contains '{slug}' but no 'params' model is provided."
                    raise ValueError(msg)

                # Check params has slug
                if "slug" not in self.params.model_fields:
                    msg = "Page params model must contain a 'slug' field when path contains '{slug}'."
                    raise ValueError(msg)

    def __call__(
        self,
        *,
        server_js: str,
        client_js: str,
        ssr_timeout: int,
    ) -> CompiledPage:
        from mountaineer.v2.page.compiled import CompiledPage as _CompiledPage  # noqa: PLC0415

        return _CompiledPage(
            page=self,
            server_js=server_js,
            client_js=client_js,
            ssr_timeout=ssr_timeout,
        )

    def data(self, *, ssr: bool, expose: bool = True) -> Callable[[F], F]:
        def decorator(handler: F) -> F:
            self._validate_handler_params(handler)
            definition = DataDefinition(name=handler.__name__, handler=handler, ssr=ssr, expose=expose)
            self._data.append(definition)
            return handler

        return decorator

    def action(
        self,
        *,
        update: tuple[NamedCallable, ...] | None = None,
    ) -> Callable[[F], F]:
        def decorator(handler: F) -> F:
            self._validate_handler_params(handler)
            name = handler.__name__
            if name in self._actions:
                msg = f"Action '{name}' is already registered"
                raise ValueError(msg)

            update_names: tuple[str, ...] | None = None
            if update is not None:
                data_lookup = {definition.handler: definition.name for definition in self._data}
                missing_handlers = [handler_item for handler_item in update if handler_item not in data_lookup]
                if missing_handlers:
                    missing = ", ".join(handler_item.__name__ for handler_item in missing_handlers)
                    msg = f"Unknown data loader(s) referenced in update: {missing}"
                    raise ValueError(msg)
                update_names = tuple(data_lookup[handler_item] for handler_item in update)

            self._actions[name] = ActionDefinition(
                name=name,
                handler=handler,
                update=update_names,
            )
            return handler

        return decorator

    def _validate_handler_params(self, handler: Callable) -> None:
        if self.params is None:
            return

        sig = inspect.signature(handler)
        params = list(sig.parameters.values())
        if not params:
            msg = f"Handler '{handler.__name__}' must accept '{self.params.__name__}' as the first argument."
            raise ValueError(msg)

        # Check annotation
        first_param = params[0]
        if first_param.annotation != self.params:
            msg = f"Handler '{handler.__name__}' first argument must be of type '{self.params.__name__}'."
            raise ValueError(msg)
