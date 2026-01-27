from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable, Protocol, TYPE_CHECKING, TypeVar

from mountaineer.v2.page.action import ActionDefinition
from mountaineer.v2.page.data import DataDefinition

if TYPE_CHECKING:
    from mountaineer.v2.page.compiled import CompiledPage


class NamedCallable(Protocol):
    __name__: str

    def __call__(self, *args: object, **kwargs: object) -> Awaitable[object]: ...


F = TypeVar("F", bound=NamedCallable)


@dataclass(slots=True, kw_only=True)
class Page:
    view: Path
    path: str
    _data: list[DataDefinition[object]] = field(default_factory=list)
    _actions: dict[str, ActionDefinition] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.path.startswith("/"):
            raise ValueError("Page path must start with '/'")
        if self.path == "/":
            return  # Root path is valid
        trimmed = self.path[1:]
        if any(segment == "" for segment in trimmed.split("/")):
            raise ValueError("Page path must not contain empty segments")

    def __call__(
        self, *, server_js: str, client_js: str, ssr_timeout: int
    ) -> CompiledPage:
        from mountaineer.v2.page.compiled import CompiledPage

        return CompiledPage(
            page=self,
            server_js=server_js,
            client_js=client_js,
            ssr_timeout=ssr_timeout,
        )

    def data(self, *, ssr: bool) -> Callable[[F], F]:
        def decorator(handler: F) -> F:
            definition = DataDefinition(name=handler.__name__, handler=handler, ssr=ssr)
            self._data.append(definition)
            return handler

        return decorator

    def action(
        self, *, update: tuple[NamedCallable, ...] | None = None
    ) -> Callable[[F], F]:
        def decorator(handler: F) -> F:
            name = handler.__name__
            if name in self._actions:
                raise ValueError(f"Action '{name}' is already registered")

            update_names: tuple[str, ...] | None = None
            if update is not None:
                data_lookup = {
                    definition.handler: definition.name for definition in self._data
                }
                missing_handlers = [
                    handler_item
                    for handler_item in update
                    if handler_item not in data_lookup
                ]
                if missing_handlers:
                    missing = ", ".join(
                        handler_item.__name__ for handler_item in missing_handlers
                    )
                    raise ValueError(
                        f"Unknown data loader(s) referenced in update: {missing}"
                    )
                update_names = tuple(data_lookup[handler_item] for handler_item in update)

            self._actions[name] = ActionDefinition(
                name=name,
                handler=handler,
                update=update_names,
            )
            return handler

        return decorator
