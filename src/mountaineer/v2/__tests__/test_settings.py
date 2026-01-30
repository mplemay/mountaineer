from mountaineer.v2.settings import Settings


def test_settings_defaults(tmp_path):
    """
    Test that settings load with correct defaults.
    """
    # We need to provide required fields
    s = Settings(
        view_root=tmp_path / "views",
        node_modules_path=tmp_path / "node_modules",
    )

    assert s.PRODUCTION is False
    assert s.ssr_timeout == 10
    assert s.live_reload_port == 0
    assert s.public_path == "/static"


def test_settings_env_override(monkeypatch, tmp_path):
    """
    Test that environment variables override defaults.
    """
    monkeypatch.setenv("MOUNTAINEER_SSR_TIMEOUT", "25")
    monkeypatch.setenv("MOUNTAINEER_PRODUCTION", "true")

    s = Settings(
        view_root=tmp_path / "views",
        node_modules_path=tmp_path / "node_modules",
    )

    assert s.ssr_timeout == 25
    assert s.PRODUCTION is True


def test_environment_property(tmp_path):
    """
    Test the helper property that converts PRODUCTION bool to string.
    """
    s_dev = Settings(
        view_root=tmp_path,
        node_modules_path=tmp_path,
        PRODUCTION=False,
    )
    assert s_dev.environment == "development"

    s_prod = Settings(
        view_root=tmp_path,
        node_modules_path=tmp_path,
        PRODUCTION=True,
    )
    assert s_prod.environment == "production"
