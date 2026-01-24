import importlib
from pathlib import Path

from mountaineer.development.packages import package_path_to_module


class ModuleReloader:
    def __init__(self, *, package: str):
        self.package = package

    def modules_from_paths(self, files: list[Path]) -> list[str]:
        modules: list[str] = []
        for file_path in files:
            try:
                module = package_path_to_module(package=self.package, file_path_raw=file_path)
            except ValueError:
                continue
            modules.append(module)

        return sorted(set(modules), key=lambda name: name.count("."), reverse=True)

    def reload_modules(self, modules: list[str]) -> bool:
        for module_name in modules:
            try:
                module = importlib.import_module(name=module_name)
                importlib.reload(module)
            except Exception:
                return False
        return True
