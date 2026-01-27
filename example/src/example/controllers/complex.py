from pathlib import Path
from uuid import UUID, uuid4

from fastapi import Request
from pydantic import BaseModel

from mountaineer import Metadata, Page


class ComplexParams(BaseModel):
    detail_id: UUID
    delay_loops: int | None = None
    throw_client_error: bool = False


page = Page(
    view=Path("app/complex/page.tsx"),
    path="/complex/{detail_id}/",
    params=ComplexParams,
)


@page.data(ssr=True, name="client_ip")
async def get_client_ip(params: ComplexParams, request: Request) -> str:
    return request.client.host if request.client else "unknown"


@page.data(ssr=True, name="random_uuid")
async def get_random_uuid(params: ComplexParams) -> UUID:
    return uuid4()


@page.data(ssr=True, name="delay_loops")
async def get_delay_loops(params: ComplexParams) -> int:
    return params.delay_loops or 0


@page.data(ssr=True, name="throw_client_error")
async def get_throw_client_error(params: ComplexParams) -> bool:
    return params.throw_client_error


@page.metadata
async def get_metadata(params: ComplexParams) -> Metadata:
    return Metadata(title=f"Complex: {params.detail_id}")
