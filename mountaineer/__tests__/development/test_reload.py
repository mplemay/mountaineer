from pathlib import Path

from mountaineer.development.reload import ModuleReloader


def test_modules_from_paths():
    reloader = ModuleReloader(package="mountaineer")
    package_root = Path(__file__).resolve().parents[2]
    cli_path = package_root / "cli.py"

    modules = reloader.modules_from_paths([cli_path])
    assert "mountaineer.cli" in modules


def test_reload_modules_success():
    reloader = ModuleReloader(package="mountaineer")
    assert reloader.reload_modules(["mountaineer.logging"])
