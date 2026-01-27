import asyncio
from pathlib import Path
from typing import AsyncIterator

from pydantic import BaseModel

from mountaineer import Page


class StreamActionResponse(BaseModel):
    value: str


page = Page(view=Path("app/stream/page.tsx"), path="/stream")


@page.action
async def stream_action() -> AsyncIterator[StreamActionResponse]:
    for i in range(10):
        yield StreamActionResponse(value=f"streaming {i}\n")
        await asyncio.sleep(1)
