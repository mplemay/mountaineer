from pathlib import Path

import pytest
from mountaineer.v2 import Page


def test_page_registration():
    """
    Test basic page creation and data loader registration.
    """
    p = Page(view=Path("views/test.tsx"), path="/test")

    @p.data(ssr=True)
    async def load_data():
        return {"key": "value"}

    assert len(p._data) == 1
    assert p._data[0].name == "load_data"
    assert p._data[0].ssr is True
    # Ensure the original function is preserved
    assert load_data.__name__ == "load_data"


def test_page_action_registration():
    """
    Test action registration and update dependency resolution.
    """
    p = Page(view=Path("views/test.tsx"), path="/test")

    @p.data(ssr=True)
    async def get_items():
        pass

    @p.action(update=(get_items,))
    async def add_item():
        pass

    assert "add_item" in p._actions
    action_def = p._actions["add_item"]
    assert action_def.name == "add_item"
    assert action_def.update == ("get_items",)


def test_page_action_unknown_update_dependency():
    """
    Test that referencing an unregistered data loader in update raises an error.
    """
    p = Page(view=Path("views/test.tsx"), path="/test")

    async def unregistered_loader():
        pass

    with pytest.raises(ValueError, match=r"Unknown data loader\(s\) referenced in update: unregistered_loader"):

        @p.action(update=(unregistered_loader,))
        async def my_action():
            pass


def test_page_duplicate_action_name():
    p = Page(view=Path("views/test.tsx"), path="/test")

    @p.action()
    async def my_action():
        pass

    with pytest.raises(ValueError, match="Action 'my_action' is already registered"):

        @p.action()
        async def my_action():
            pass


def test_page_call_creates_compiled_page():
    """
    Test that calling the Page instance creates a CompiledPage with injected bundles.
    """
    p = Page(view=Path("views/test.tsx"), path="/test")
    compiled = p(
        server_js="server_code",
        client_js="client_code",
        ssr_timeout=15,
    )

    assert compiled.server_js == "server_code"
    assert compiled.client_js == "client_code"
    assert compiled.ssr_timeout == 15
    assert compiled.page is p
