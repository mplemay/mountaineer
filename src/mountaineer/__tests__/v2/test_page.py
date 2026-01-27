from pathlib import Path

import pytest

from mountaineer.v2.page.compiled import CompiledPage
from mountaineer.v2.page.core import Page


def test_page_data_registration_order() -> None:
    page = Page(view=Path("views/Post.tsx"), path="/post/{post_id}")

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
    page = Page(view=Path("views/Post.tsx"), path="/post/{post_id}")

    @page.data(ssr=True)
    async def get_post() -> str:
        return "ok"

    @page.action(update=(get_post,))
    async def refresh() -> int:
        return 1

    assert page._actions["refresh"].update == ("get_post",)
    assert page._actions["refresh"].handler is refresh


def test_page_action_rejects_unknown_updates() -> None:
    page = Page(view=Path("views/Post.tsx"), path="/post/{post_id}")

    async def missing_loader() -> int:
        return 0

    with pytest.raises(ValueError, match="Unknown data loader"):
        page.action(update=(missing_loader,))(missing_loader)


def test_page_action_rejects_duplicate_names() -> None:
    page = Page(view=Path("views/Post.tsx"), path="/post/{post_id}")

    @page.action()
    async def do_work() -> None:
        return None

    with pytest.raises(ValueError, match="already registered"):
        page.action()(do_work)


def test_page_call_returns_compiled_page() -> None:
    page = Page(view=Path("views/Post.tsx"), path="/post/{post_id}")

    compiled = page(server_js="server", client_js="client", ssr_timeout=5)

    assert isinstance(compiled, CompiledPage)
    assert compiled.page is page
    assert compiled.server_js == "server"
    assert compiled.client_js == "client"
    assert compiled.ssr_timeout == 5


def test_page_decorators_preserve_function_identity() -> None:
    page = Page(view=Path("views/Post.tsx"), path="/post/{post_id}")

    async def loader() -> int:
        return 1

    async def action() -> int:
        return 2

    decorated_loader = page.data(ssr=True)(loader)
    decorated_action = page.action()(action)

    assert decorated_loader is loader
    assert decorated_action is action
    assert decorated_loader.__annotations__ == loader.__annotations__
    assert decorated_action.__annotations__ == action.__annotations__


def test_page_path_validation() -> None:
    with pytest.raises(ValueError, match="must start with"):
        Page(view=Path("views/Post.tsx"), path="post/{post_id}")

    with pytest.raises(ValueError, match="empty segments"):
        Page(view=Path("views/Post.tsx"), path="/post/")

    with pytest.raises(ValueError, match="empty segments"):
        Page(view=Path("views/Post.tsx"), path="/post//details")


def test_page_root_path_is_valid() -> None:
    page = Page(view=Path("views/Home.tsx"), path="/")
    assert page.path == "/"
