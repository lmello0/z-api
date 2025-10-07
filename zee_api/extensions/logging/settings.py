from pydantic_settings import BaseSettings, SettingsConfigDict


class LoggingModuleSettings(BaseSettings):
    log_level: str = "INFO"
    log_contexts: list[str] = ["correlation_id", "request_id", "trace_id", "user_id"]

    model_config = SettingsConfigDict(frozen=True, extra="ignore")
