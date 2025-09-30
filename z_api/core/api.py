from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from z_api.core.config.settings import Settings
from z_api.core.logging.config import LogConfig
from z_api.core.plugin.plugin import activate_plugins


def create_app(*, settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or Settings()

    log_config = LogConfig(settings)
    log_config.configure()

    active_plugins = []

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal active_plugins
        active_plugins = activate_plugins(app, settings)

        try:
            yield
        finally:
            for p in reversed(active_plugins):
                fn = getattr(p, "on_shutdown", False)
                if callable(fn):
                    await fn(app)

    app = FastAPI(
        title=settings.app_name,
        docs_url=f"{settings.context_path}/swagger",
        redoc_url=f"{settings.context_path}/redoc",
        openapi_url=f"{settings.context_path}/openapi",
        lifespan=lifespan,
    )

    return app
