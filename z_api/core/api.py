from typing import Optional

from fastapi import FastAPI

from z_api.core.config.settings import Settings


def create_app(*, settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or Settings()

    app = FastAPI(
        title=settings.app_name,
        docs_url=f"{settings.context_path}/swagger",
        redoc_url=f"{settings.context_path}/redoc",
        openapi_url=f"{settings.context_path}/openapi",
    )

    return app
