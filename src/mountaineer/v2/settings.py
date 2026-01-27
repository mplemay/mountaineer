from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Env vars: MOUNTAINEER_VIEW_ROOT, MOUNTAINEER_NODE_MODULES_PATH
    view_root: Path
    node_modules_path: Path
    # Env vars: MOUNTAINEER_PRODUCTION, MOUNTAINEER_LIVE_RELOAD_PORT
    PRODUCTION: bool = False
    live_reload_port: int = 0
    # Env vars: MOUNTAINEER_PUBLIC_PATH, MOUNTAINEER_SSR_TIMEOUT
    public_path: str = "/static"
    ssr_timeout: int = 10

    model_config = SettingsConfigDict(
        env_prefix="MOUNTAINEER_",
        env_file=".env",
        extra="ignore",
    )

    @field_validator("view_root", "node_modules_path", mode="before")
    @classmethod
    def _validate_required_path(cls, value: object) -> object:
        if isinstance(value, str) and value.strip() == "":
            msg = "Path values cannot be empty"
            raise ValueError(msg)
        return value

    @field_validator("ssr_timeout")
    @classmethod
    def _validate_ssr_timeout(cls, value: int) -> int:
        if value <= 0:
            msg = "ssr_timeout must be positive"
            raise ValueError(msg)
        return value

    @property
    def environment(self) -> str:
        return "production" if self.PRODUCTION else "development"
