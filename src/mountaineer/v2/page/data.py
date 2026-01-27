from dataclasses import dataclass
from typing import Awaitable, Callable, Generic, TypeVar

T = TypeVar("T")


@dataclass(slots=True, kw_only=True)
class DataDefinition(Generic[T]):
    name: str
    handler: Callable[..., Awaitable[T]]
    ssr: bool
