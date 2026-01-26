from mountaineer.config import ConfigBase


class AppConfig(ConfigBase):
    PACKAGE: str | None = "example"
