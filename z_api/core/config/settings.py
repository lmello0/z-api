from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Z-API"
    app_version: str = "0.1.0"
    app_env: str = "dev"

    context_path: str = "/z-api"

    class Config:
        env_prefix = "APP_"
        case_sensitive = False
