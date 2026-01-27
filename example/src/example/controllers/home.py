from pathlib import Path
from uuid import UUID, uuid4

from fastapi import Request
from pydantic import BaseModel

from mountaineer import Metadata, Page


class IncrementCountRequest(BaseModel):
    count: int


class GetExternalDataResponse(BaseModel):
    first_name: str


page = Page(view=Path("app/home/page.tsx"), path="/")

_global_count = 0


@page.data(ssr=True, name="client_ip")
async def get_client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@page.data(ssr=True, name="current_count")
async def get_current_count() -> int:
    return _global_count


@page.data(ssr=True, name="random_uuid")
async def get_random_uuid() -> UUID:
    return uuid4()


@page.metadata
async def get_metadata() -> Metadata:
    return Metadata(title="Home")


@page.action(update=(get_client_ip, get_current_count, get_random_uuid))
async def increment_count(payload: IncrementCountRequest) -> None:
    global _global_count
    _global_count += payload.count


@page.action(update=(get_current_count,))
async def increment_count_only(payload: IncrementCountRequest, url_param: int) -> None:
    global _global_count
    _global_count += payload.count


@page.action
async def get_external_data() -> GetExternalDataResponse:
    return GetExternalDataResponse(first_name="John")
