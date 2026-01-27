from dataclasses import dataclass
from typing import Awaitable, Callable


@dataclass(slots=True, kw_only=True)
class ActionDefinition:
    name: str
    handler: Callable[..., Awaitable[object]]
    update: tuple[str, ...] | None
