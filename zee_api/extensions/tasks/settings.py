from pydantic_settings import BaseSettings, SettingsConfigDict


class TaskModuleSettings(BaseSettings):
    task_package: str

    model_config = SettingsConfigDict(frozen=True, extra="ignore")
