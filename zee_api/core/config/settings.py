from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


class Settings(BaseSettings):
    app_name: str = "Z-API"
    app_version: str = "0.1.0"
    app_env: str = "dev"

    context_path: str = "/z-api"

    log_config_path: str = "resources/logging.yaml"

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
