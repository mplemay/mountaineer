import pytest
from pydantic import BaseModel

from mountaineer.actions.fields import FunctionActionType, get_function_metadata
from mountaineer.actions.sideeffect_dec import sideeffect
from mountaineer.annotation_helpers import MountaineerUnsetValue
from mountaineer.controller import ControllerBase
from mountaineer.render import RenderBase


class ExampleRenderModel(RenderBase):
    value_a: str
    value_b: str


def test_markup_sideeffect():
    class ExamplePassthroughModel(BaseModel):
        first_name: str

    class TestController(ControllerBase):
        view_path = "/test.tsx"

        @sideeffect(reload=tuple([ExampleRenderModel.value_a]))
        def sideeffect_and_return_data(self) -> ExamplePassthroughModel:
            return ExamplePassthroughModel(first_name="John")

    metadata = get_function_metadata(TestController.sideeffect_and_return_data)
    assert metadata.action_type == FunctionActionType.SIDEEFFECT
    assert metadata.get_passthrough_model() == ExamplePassthroughModel
    assert metadata.function_name == "sideeffect_and_return_data"
    assert metadata.reload_states == tuple([ExampleRenderModel.value_a])
    assert metadata.reload_action
    assert isinstance(metadata.render_model, MountaineerUnsetValue)


@pytest.mark.asyncio
async def test_sideeffect_returns_reload():
    class ExampleController(ControllerBase):
        view_path = "/test.tsx"

        @sideeffect
        def call_sideeffect(self, payload: dict) -> None:
            pass

    controller = ExampleController()
    result = await controller.call_sideeffect({})
    assert result == {"passthrough": None, "reload": []}


@pytest.mark.asyncio
async def test_sideeffect_returns_named_reload():
    class ExampleController(ControllerBase):
        view_path = "/test.tsx"

        @sideeffect(reload=tuple([ExampleRenderModel.value_a]))
        def call_sideeffect(self, payload: dict) -> None:
            pass

    controller = ExampleController()
    result = await controller.call_sideeffect({})
    assert result == {"passthrough": None, "reload": ["value_a"]}


@pytest.mark.asyncio
async def test_sideeffect_original_access():
    class ExampleController(ControllerBase):
        view_path = "/test.tsx"

        @sideeffect
        def call_sideeffect(self, payload: dict) -> None:
            pass

    controller = ExampleController()
    await ExampleController.call_sideeffect.original(controller, {})
