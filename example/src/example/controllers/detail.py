from pathlib import Path
from uuid import UUID

from fastapi import Request
from pydantic import BaseModel

from mountaineer import Metadata, Page


class DetailParams(BaseModel):
    detail_id: UUID


page = Page(
    view=Path("app/detail/page.tsx"),
    path="/detail/{detail_id}/",
    params=DetailParams,
)


@page.data(ssr=True, name="client_ip")
async def get_client_ip(params: DetailParams, request: Request) -> str:
    return request.client.host if request.client else "unknown"


@page.metadata
async def get_metadata(params: DetailParams) -> Metadata:
    return Metadata(title=f"Detail: {params.detail_id}")
