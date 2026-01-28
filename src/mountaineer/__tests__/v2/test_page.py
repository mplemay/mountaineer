from pathlib import Path

import pytest
from pydantic import BaseModel

from mountaineer.v2.page.compiled import CompiledPage
from mountaineer.v2.page.core import Page


class PostParams(BaseModel):
    slug: str


def test_page_data_registration_order() -> None:
    page = Page(view=Path("views/Post.tsx"), path="/post")

    @page.data(ssr=True)
    async def first_loader() -> int:
        return 1

    @page.data(ssr=False)
    async def second_loader() -> int:
        return 2

    assert [definition.name for definition in page._data] == [
        "first_loader",
        "second_loader",
    ]
    assert page._data[0].ssr is True
    assert page._data[1].ssr is False
    assert page._data[0].handler is first_loader
    assert page._data[1].handler is second_loader


def test_page_action_registration_and_update_mapping() -> None:
    page = Page(view=Path("views/Post.tsx"), path="/post")

    @page.data(ssr=True)
    async def get_post() -> str:
        return "ok"

    @page.action(update=(get_post,))
    async def refresh() -> int:
        return 1

    assert page._actions["refresh"].update == ("get_post",)
    assert page._actions["refresh"].handler is refresh


def test_page_action_rejects_unknown_updates() -> None:
    page = Page(view=Path("views/Post.tsx"), path="/post")

    async def missing_loader() -> int:
        return 0

    with pytest.raises(ValueError, match="Unknown data loader"):
        page.action(update=(missing_loader,))(missing_loader)


def test_page_action_rejects_duplicate_names() -> None:
    page = Page(view=Path("views/Post.tsx"), path="/post")

    @page.action()
    async def do_work() -> None:
        return None

    with pytest.raises(ValueError, match="already registered"):
        page.action()(do_work)


def test_page_call_returns_compiled_page() -> None:
    page = Page(view=Path("views/Post.tsx"), path="/post")

    compiled = page(server_js="server", client_js="client", ssr_timeout=5)

    assert isinstance(compiled, CompiledPage)
    assert compiled.page is page
    assert compiled.server_js == "server"
    assert compiled.client_js == "client"
    assert compiled.ssr_timeout == 5


def test_page_decorators_preserve_function_identity() -> None:
    page = Page(view=Path("views/Post.tsx"), path="/post")

    async def loader() -> int:
        return 1

    async def action() -> int:
        return 2

    decorated_loader = page.data(ssr=True)(loader)
    decorated_action = page.action()(action)

    assert decorated_loader is loader
    assert decorated_action is action


def test_page_path_validation() -> None:
    with pytest.raises(ValueError, match="must start with"):
        Page(view=Path("views/Post.tsx"), path="post")

    with pytest.raises(ValueError, match="empty segments"):
        Page(view=Path("views/Post.tsx"), path="/post/")

    with pytest.raises(ValueError, match="empty segments"):
        Page(view=Path("views/Post.tsx"), path="/post//details")

    # Valid root
    Page(view=Path("views/Home.tsx"), path="/")


def test_page_path_params_validation() -> None:
    # 1. Reject non-slug param name
    with pytest.raises(ValueError, match="must be named '{slug}'"):
        Page(view=Path("views/Post.tsx"), path="/post/{id}")

    # 2. Reject multiple params
    with pytest.raises(ValueError, match="Only one dynamic path segment"):
        Page(view=Path("views/Post.tsx"), path="/post/{slug}/{other}")

    # 3. Require params model if slug is present
    with pytest.raises(ValueError, match="no 'params' model"):
        Page(view=Path("views/Post.tsx"), path="/post/{slug}")

    # 4. Require slug field in params model
    class NoSlug(BaseModel):
        id: int

    with pytest.raises(ValueError, match="must contain a 'slug' field"):
        Page(view=Path("views/Post.tsx"), path="/post/{slug}", params=NoSlug)

    # 5. Success
    Page(view=Path("views/Post.tsx"), path="/post/{slug}", params=PostParams)


def test_handler_params_validation() -> None:
    page = Page(view=Path("views/Post.tsx"), path="/post/{slug}", params=PostParams)

    # Success
    @page.data(ssr=True)
    async def valid_handler(params: PostParams) -> int:
        return 1

    # Fail: No args
    with pytest.raises(ValueError, match="must accept 'PostParams'"):

        @page.data(ssr=True)
        async def no_args() -> int:
            return 1

    # Fail: Wrong type
    with pytest.raises(ValueError, match="first argument must be of type 'PostParams'"):

        @page.data(ssr=True)
        async def wrong_type(params: int) -> int:
            return 1
