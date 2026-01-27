from collections.abc import Awaitable, Callable
from dataclasses import dataclass


@dataclass(slots=True, kw_only=True)
class ActionDefinition:
    name: str
    handler: Callable[..., Awaitable[object]]
    update: tuple[str, ...] | None
