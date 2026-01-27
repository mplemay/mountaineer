from pathlib import Path

import pytest
from pydantic import ValidationError

from mountaineer.v2.settings import Settings


def test_settings_defaults() -> None:
    settings = Settings(view_root=Path("views"), node_modules_path=Path("node_modules"))

    assert settings.PRODUCTION is False
    assert settings.live_reload_port == 0
    assert settings.public_path == "/static"
    assert settings.ssr_timeout == 10
    assert isinstance(settings.view_root, Path)
    assert isinstance(settings.node_modules_path, Path)


def test_settings_environment_helper() -> None:
    settings = Settings(view_root=Path("views"), node_modules_path=Path("node_modules"))
    assert settings.environment == "development"

    prod_settings = Settings(
        view_root=Path("views"),
        node_modules_path=Path("node_modules"),
        PRODUCTION=True,
    )
    assert prod_settings.environment == "production"


def test_settings_env_precedence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "MOUNTAINEER_VIEW_ROOT=views_from_env_file\n"
        "MOUNTAINEER_NODE_MODULES_PATH=node_modules_from_env_file\n"
        "MOUNTAINEER_SSR_TIMEOUT=12\n",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MOUNTAINEER_VIEW_ROOT", "views_from_env_var")
    monkeypatch.setenv("MOUNTAINEER_SSR_TIMEOUT", "15")
    monkeypatch.setenv("MOUNTAINEER_UNKNOWN", "ignored")

    settings = Settings()

    assert settings.view_root == Path("views_from_env_var")
    assert settings.node_modules_path == Path("node_modules_from_env_file")
    assert settings.ssr_timeout == 15


def test_settings_invalid_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "MOUNTAINEER_VIEW_ROOT=views\n"
        "MOUNTAINEER_NODE_MODULES_PATH=node_modules\n"
        "MOUNTAINEER_SSR_TIMEOUT=not-a-number\n",
    )

    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize(
    ("view_root_value", "node_modules_value"),
    [
        ("", "node_modules"),
        ("views", ""),
    ],
)
def test_settings_empty_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    view_root_value: str,
    node_modules_value: str,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                f"MOUNTAINEER_VIEW_ROOT={view_root_value}",
                f"MOUNTAINEER_NODE_MODULES_PATH={node_modules_value}",
            ],
        )
        + "\n",
    )

    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValidationError):
        Settings()
