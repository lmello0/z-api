from functools import lru_cache

from pydantic import BaseModel
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

from zee_api.extensions.http.settings import HttpSettings


class LogConfig(BaseModel):
    log_level: str = "INFO"
    log_config_path: str = "resources/logging.yaml"
    log_contexts: list[str] = ["correlation_id", "request_id", "trace_id", "user_id"]


class Settings(BaseSettings):
    app_name: str = "Z-API"
    app_version: str = "0.1.0"
    app_env: str = "dev"

    app_context_path: str = "/z-api"

    log_config: LogConfig = LogConfig()

    http_config: HttpSettings = HttpSettings()

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        case_sensitive=False,
        frozen=True,
        yaml_file="resources/application_config.yaml",
        extra="allow",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (YamlConfigSettingsSource(settings_cls),)


@lru_cache
def get_app_settings() -> Settings:
    return Settings()
