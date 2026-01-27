from pathlib import Path

from fastapi import FastAPI
from mountaineer.v2 import Mountaineer, Page, Settings

settings = Settings(
    view_root=Path(__file__).parent / "views",
    node_modules_path=Path(__file__).parent / "views" / "node_modules",
    PRODUCTION=False,
)

# Define pages
home_page = Page(view=Path("home/page.tsx"), path="/")
detail_page = Page(view=Path("detail/page.tsx"), path="/detail/{detail_id}")

# Create Mountaineer app
mountaineer = Mountaineer(settings=settings)
mountaineer.include_page(page=home_page)
mountaineer.include_page(page=detail_page)

# Mount into FastAPI
app = FastAPI()
app.mount(path="/", app=mountaineer, name="website")
