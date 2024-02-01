from pathlib import Path

import pytest
from fastapi import Depends, Request
from pydantic.main import BaseModel
from starlette.datastructures import Headers

from filzl.actions.fields import FunctionActionType, get_function_metadata
from filzl.actions.sideeffect import get_render_parameters, sideeffect
from filzl.app import AppController
from filzl.controller import ControllerBase
from filzl.render import RenderBase


def test_markup_sideeffect():
    """
    Check that the @sideeffect decorator extracts the expected
    data from our model definition.
    """

    class ExampleRenderModel(RenderBase):
        value_a: str
        value_b: str

    class ExamplePassthroughModel(BaseModel):
        first_name: str

    class TestController(ControllerBase):
        # We declare as complicated a payload as @sideeffect supports so we can
        # see the full amount of metadata properties that are set
        @sideeffect(
            response_model=ExamplePassthroughModel,
            reload=tuple([ExampleRenderModel.value_a]),
        )
        def sideeffect_and_return_data(self):
            return dict(
                first_name="John",
            )

    metadata = get_function_metadata(TestController.sideeffect_and_return_data)
    assert metadata.action_type == FunctionActionType.SIDEEFFECT
    assert metadata.get_passthrough_model() == ExamplePassthroughModel
    assert metadata.function_name == "sideeffect_and_return_data"
    assert metadata.reload_states == tuple([ExampleRenderModel.value_a])
    assert metadata.render_model is None
    assert metadata.url is None
    assert metadata.return_model is None
    assert metadata.render_router is None


@pytest.mark.asyncio
async def test_get_render_parameters():
    """
    Given a controller, reproduce the logic of FastAPI to sniff the render()
    function for dependencies and resolve them.

    """
    found_cookie = None

    def grab_cookie_dependency(request: Request):
        nonlocal found_cookie
        found_cookie = request.cookies.get("test-cookie")
        return found_cookie

    class ExampleRenderModel(RenderBase):
        value_a: str
        value_b: str

    class TestController(ControllerBase):
        url: str = "/test/{query_id}/"

        def render(
            self,
            query_id: int,
            cookie_dependency: str = Depends(grab_cookie_dependency),
        ) -> ExampleRenderModel:
            return dict(
                value_a="Hello",
                value_b="World",
            )

    # We need to load this test controller to an actual application runtime
    # or else we don't have the render() metadata added
    app = AppController(Path())
    controller = TestController()
    app.register(controller)

    fake_request = Request(
        {
            "type": "http",
            "headers": Headers(
                {
                    "cookie": "test-cookie=cookie-value",
                    # Its important the referer aligns with the controller url, since that is expected
                    # to be the original view page that is calling this sub-function
                    "referer": "http://example.com/test/5/",
                }
            ).raw,
            "http_version": "1.1",
            "scheme": "",
            "client": "",
            "server": "",
            # The URL and method should both be different, to test whether we are able
            # to map the request to the correct endpoint
            "method": "POST",
            "url": "http://localhost/related_action_endpoint",
        }
    )

    async with get_render_parameters(controller, fake_request) as resolved_dependencies:
        assert resolved_dependencies == {
            "cookie_dependency": "cookie-value",
            "query_id": 5,
        }
