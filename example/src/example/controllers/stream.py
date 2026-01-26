import asyncio
from typing import AsyncIterator

from pydantic import BaseModel

from mountaineer import ControllerBase, passthrough


class StreamActionResponse(BaseModel):
    value: str


class StreamController(ControllerBase):
    url = "/stream"
    view_path = "/app/stream/page.tsx"

    async def render(self) -> None:
        pass

    @passthrough
    async def stream_action(self) -> AsyncIterator[StreamActionResponse]:
        for i in range(10):
            yield StreamActionResponse(value=f"streaming {i}\n")
            await asyncio.sleep(1)
