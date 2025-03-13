from dataclasses import dataclass
from pathlib import Path

from mountaineer.development.messages_broker import IsolatedMessageBase


@dataclass
class ErrorResponse:
    """Generic error response"""

    exception: str
    traceback: str


@dataclass
class SuccessResponse:
    """Generic success response"""

    pass


@dataclass
class BootupMessage(IsolatedMessageBase[SuccessResponse | ErrorResponse]):
    """Message to bootup the isolated app context"""

    pass


@dataclass
class StartServerMessage(IsolatedMessageBase[SuccessResponse | ErrorResponse]):
    """Message to start the server"""

    host: str
    port: int
    live_reload_port: int


@dataclass
class BuildJsMessage(IsolatedMessageBase[SuccessResponse | ErrorResponse]):
    """Message to trigger JS compilation"""

    updated_js: list[Path] | None


@dataclass
class BuildUseServerMessage(IsolatedMessageBase[SuccessResponse | ErrorResponse]):
    """Message to build the useServer support files"""

    pass


MessageTypes = (
    BootupMessage | StartServerMessage | BuildJsMessage | BuildUseServerMessage
)
