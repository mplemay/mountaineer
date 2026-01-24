import pytest

from mountaineer.config import unregister_config

from {{project_name}}.config import AppConfig


@pytest.fixture(autouse=True)
def config():
    """
    Test-time configuration. Set to auto-use the fixture so that the configuration
    is mounted and exposed to the dependency injection framework in all tests.

    """
    unregister_config()
    return AppConfig(
        # Ignore the actual defaults
        _env_file=".env.test",  # type: ignore
    )
