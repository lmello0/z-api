from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from zee_api.core.config.settings import Settings
from zee_api.core.logging.config import LogConfig


def create_app(*, settings: Optional[Settings] = None) -> FastAPI:
    """
    Create a FastAPI instance using given settings.

    Args:
        settings: A instance of `z_api.Settings`

    Returns
        A FastAPI instance
    """

    settings = settings or Settings()

    log_config = LogConfig(settings)
    log_config.configure()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield

    app = FastAPI(
        title=settings.app_name,
        docs_url=f"{settings.context_path}/swagger",
        redoc_url=f"{settings.context_path}/redoc",
        openapi_url=f"{settings.context_path}/openapi",
        lifespan=lifespan,
    )

    return app
