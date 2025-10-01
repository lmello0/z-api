import logging
from contextlib import asynccontextmanager
from typing import Any, Callable, Optional, Self

from fastapi import APIRouter, FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ExceptionHandler

from zee_api.core.config.settings import get_app_settings
from zee_api.core.logging.context.log_context_registry import (
    get_log_context_registry,
)
from zee_api.core.logging.log_configurator import get_log_configurator
from zee_api.extensions.tasks.task_registry import get_task_registry

logger = logging.getLogger(__name__)


class ZeeApi:
    def __init__(
        self,
    ):
        self.settings = get_app_settings()
        self.app = None

        self._log_context_registry = None
        self._log_configurator = None

        self._lifespan = None

        self._task_registry = None

        self._middlewares = []
        self._routes = []
        self._exception_handlers = []

    def configure_default_logging(self) -> Self:
        self._log_context_registry = get_log_context_registry()
        for context in self.settings.log_config.log_contexts:
            self._log_context_registry.register_builtin(context)

        self._log_configurator = get_log_configurator()
        self._log_configurator.configure()

        return self

    def add_task_scheduler(self, tasks_package: str) -> Self:
        self._task_registry = get_task_registry()

        self._task_registry.discover_tasks(tasks_package)
        self._task_registry.setup_all_tasks()

        return self

    def add_lifespan(
        self,
        use_default: bool = True,
        lifespan: Optional[Callable[[Any], Any]] = None,
    ) -> Self:
        if use_default:

            @asynccontextmanager
            async def default_lifespan(app: FastAPI):
                if self._task_registry:
                    self._task_registry.start_scheduler()

                yield

                if self._task_registry:
                    self._task_registry.shutdown_scheduler()

            self.lifespan = default_lifespan
            return self

        if not lifespan:
            raise ValueError(
                "If use_default equals False, a lifespan function is required"
            )

        self.lifespan = lifespan

        return self

    def add_middleware(self, middleware: BaseHTTPMiddleware) -> Self:
        self._middlewares.append(middleware)

        return self

    def add_route(self, api_router: APIRouter) -> Self:
        self._routes.append(api_router)

        return self

    def add_exception_handler(
        self, exception_class: int | type[Exception], handler: ExceptionHandler
    ) -> Self:
        self._exception_handlers.append((exception_class, handler))

        return self

    def build(
        self,
        title: Optional[str] = None,
        docs_url: Optional[str] = None,
        redoc_url: Optional[str] = None,
        openapi_url: Optional[str] = None,
    ) -> FastAPI:
        self.app = FastAPI(
            title=title or self.settings.app_name,
            docs_url=docs_url or f"{self.settings.app_context_path}/swagger",
            redoc_url=redoc_url or f"{self.settings.app_context_path}/redoc",
            openapi_url=openapi_url or f"{self.settings.app_context_path}/openapi",
            lifespan=self.lifespan,
        )

        if self._log_context_registry:
            log_middlewares = self._log_context_registry.get_all_middlewares()
            for _, middleware_class in log_middlewares.items():
                self.app.add_middleware(middleware_class)

        for middleware in self._middlewares:
            self.app.add_middleware(middleware)

        for router in self._routes:
            self.app.include_router(router)

        for clazz, handler in self._exception_handlers:
            self.app.add_exception_handler(clazz, handler)

        return self.app
