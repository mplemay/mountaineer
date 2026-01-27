from pathlib import Path

import pytest
from fastapi import Body, Request
from pydantic import BaseModel

from mountaineer import Metadata, Page


class ExampleParams(BaseModel):
    item_id: int


def test_page_path_validation():
    with pytest.raises(ValueError, match="Non-layout pages require a path"):
        Page(view=Path("page.tsx"))

    with pytest.raises(ValueError, match="Layout pages cannot specify a path"):
        Page(view=Path("layout.tsx"), path="/", layout=True)

    Page(view=Path("page.tsx"), path="/")
    Page(view=Path("layout.tsx"), layout=True)


def test_data_requires_return_type():
    page = Page(view=Path("page.tsx"), path="/")

    with pytest.raises(ValueError, match="must have a return type annotation"):

        @page.data()
        def missing_return():
            return 1


def test_duplicate_loader_names():
    page = Page(view=Path("page.tsx"), path="/")

    @page.data(name="value")
    def first() -> int:
        return 1

    with pytest.raises(ValueError, match="Duplicate loader name"):

        @page.data(name="value")
        def second() -> int:
            return 2


def test_loader_signature_validation():
    page = Page(view=Path("page.tsx"), path="/items/{item_id}", params=ExampleParams)

    with pytest.raises(ValueError, match="must use params"):

        @page.data()
        def invalid_param(item_id: int) -> int:
            return item_id

    with pytest.raises(ValueError, match="params type must be"):

        @page.data()
        def invalid_params_type(params: str) -> int:
            return 1

    with pytest.raises(ValueError, match="marked ssr=True"):

        @page.data()
        def invalid_body(payload: str = Body(...)) -> int:
            return 1

    @page.data(ssr=False)
    def valid_body(payload: str = Body(...)) -> int:
        return 1


def test_layout_loader_restrictions():
    layout_page = Page(view=Path("layout.tsx"), layout=True)

    with pytest.raises(ValueError, match="cannot accept Request"):

        @layout_page.data()
        def invalid_request(request: Request) -> int:
            return 1


def test_action_update_validation():
    page = Page(view=Path("page.tsx"), path="/")

    @page.data()
    def loader() -> int:
        return 1

    def unknown_loader() -> int:
        return 1

    with pytest.raises(ValueError, match="not registered on this page"):

        @page.action(update=(unknown_loader,))
        def invalid_action() -> None:
            pass


def test_metadata_registration():
    page = Page(view=Path("page.tsx"), path="/")

    with pytest.raises(ValueError, match="must return Metadata"):

        @page.metadata
        def bad_metadata() -> str:
            return "nope"

    @page.metadata
    def good_metadata() -> Metadata:
        return Metadata(title="ok")

    with pytest.raises(ValueError, match="Only one metadata loader"):

        @page.metadata
        def duplicate_metadata() -> Metadata:
            return Metadata(title="dup")
