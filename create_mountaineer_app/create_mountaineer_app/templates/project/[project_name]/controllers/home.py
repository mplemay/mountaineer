{% if create_stub_files %}
from mountaineer import sideeffect, ControllerBase, Metadata, RenderBase
from pydantic import BaseModel


# In-memory storage for this example
# In a real app, you'd use a database
items_storage: list["DetailItem"] = []


class DetailItem(BaseModel):
    description: str


class HomeRender(RenderBase):
    items: list[DetailItem]


class HomeController(ControllerBase):
    url = "/"
    view_path = "/app/home/page.tsx"

    async def render(self) -> HomeRender:
        return HomeRender(
            items=items_storage,
            metadata=Metadata(title="Home"),
        )

    @sideeffect
    async def new_detail(self) -> None:
        obj = DetailItem(description="Untitled Item")
        items_storage.append(obj)
{% endif %}
