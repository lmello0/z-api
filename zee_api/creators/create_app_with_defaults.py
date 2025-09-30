from contextlib import asynccontextmanager

from fastapi import FastAPI

from zee_api.core.config.settings import Settings
from zee_api.core.logging.context.builtins.correlation_id_context import (
    CorrelationIdContext,
)
from zee_api.core.logging.context.builtins.request_id_context import RequestIdContext
from zee_api.core.logging.context.builtins.trace_id_context import TraceIdContext
from zee_api.core.logging.context.builtins.user_id_context import UserIdContext
from zee_api.core.logging.context.log_context_registry import LogContextRegistry
from zee_api.core.logging.log_configurator import LogConfigurator


def create_app() -> FastAPI:
    """
    Create a FastAPI instance using given settings.

    Args:
        settings: A instance of `z_api.Settings`

    Returns
        A FastAPI instance
    """

    settings = Settings()
    default_registry = LogContextRegistry()

    default_registry.register("correlation_id", CorrelationIdContext())
    default_registry.register("request_id", RequestIdContext())
    default_registry.register("trace_id", TraceIdContext())
    default_registry.register("user_id", UserIdContext())

    log_config = LogConfigurator(settings, default_registry)
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

    middlewares = default_registry.get_all_middlewares()
    for _, middleware_class in middlewares.items():
        app.add_middleware(middleware_class)

    return app
