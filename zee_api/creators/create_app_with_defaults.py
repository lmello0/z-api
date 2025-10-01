import logging
from contextlib import asynccontextmanager
from typing import Any, Callable, Optional

from fastapi import FastAPI

from zee_api.core.config.settings import Settings, get_app_settings
from zee_api.core.logging.context.log_context_registry import (
    LogContextRegistry,
    get_log_context_registry,
)
from zee_api.core.logging.log_configurator import get_log_configurator

logger = logging.getLogger(__name__)


def create_app_with_defaults(
    settings: Optional[Settings] = None,
    log_context_registry: Optional[LogContextRegistry] = None,
    lifespan: Optional[Callable[[Any], Any]] = None,
    title: Optional[str] = None,
    extra_middlewares: Optional[list] = None,
) -> FastAPI:
    """
    Create a FastAPI instance with the default configuration for Zee API.

    Args:
        settings: Custom settings instance. Defaults to a new `Settings` instance.
        log_context_registry: Custom log context registry. Defaults to a new `LogContextRegistry` instance.
        lifespan: Custom lifespan function. Defaults to the built-in lifespan.
        title: Custom title for the FastAPI app. Defaults to settings.app_name.
        extra_middlewares: List of additional middlewares to add to the app.

    Returns:
        A FastAPI instance.
    """
    settings = get_app_settings()

    if not log_context_registry:
        log_context_registry = get_log_context_registry()

        for context in settings.log_config.log_contexts:
            log_context_registry.register_builtin(context)

    log_configurator = get_log_configurator()
    log_configurator.configure()

    if lifespan is None:
        @asynccontextmanager
        async def default_lifespan(app: FastAPI):
            logger.info("Starting app")

            yield

            logger.info("Shutting down app...")

        lifespan = default_lifespan

    app = FastAPI(
        title=title or settings.app_name,
        docs_url=f"{settings.app_context_path}/swagger",
        redoc_url=f"{settings.app_context_path}/redoc",
        openapi_url=f"{settings.app_context_path}/openapi",
        lifespan=lifespan,
    )

    middlewares = log_context_registry.get_all_middlewares()
    for _, middleware_class in middlewares.items():
        app.add_middleware(middleware_class)

    if extra_middlewares:
        for middleware in extra_middlewares:
            app.add_middleware(middleware)

    return app
