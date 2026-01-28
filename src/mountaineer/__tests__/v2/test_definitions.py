from mountaineer.v2.page.action import ActionDefinition
from mountaineer.v2.page.data import DataDefinition


async def _data_handler() -> int:
    return 1


async def _action_handler() -> str:
    return "ok"


def test_data_definition_fields() -> None:
    definition = DataDefinition(name="get_value", handler=_data_handler, ssr=True, expose=True)

    assert definition.name == "get_value"
    assert definition.handler is _data_handler
    assert definition.ssr is True
    assert definition.expose is True


def test_action_definition_fields() -> None:
    definition = ActionDefinition(
        name="do_action",
        handler=_action_handler,
        update=("get_value", "get_other"),
    )

    assert definition.name == "do_action"
    assert definition.handler is _action_handler
    assert definition.update == ("get_value", "get_other")
