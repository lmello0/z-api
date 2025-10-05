import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Type

import psutil
from fastapi import FastAPI
from starlette.types import Receive, Scope, Send

from zee_api.core.config.settings import Settings
from zee_api.core.extension_manager.base_extension import BaseExtension
from zee_api.core.extension_manager.extension_manager import ExtensionManager
from zee_api.core.logging.context.log_context_registry import get_log_context_registry
from zee_api.core.logging.log_configurator import get_log_configurator
from zee_api.utils.format_bytes import format_bytes

logger = logging.getLogger(__name__)


class ZeeApi:
    def __init__(self) -> None:
        self.settings = Settings()

        self.extension_manager = ExtensionManager()
        self._extension_configs = {}

        self.started_at: float = float("-inf")
        self.current_process = psutil.Process(os.getpid())

        log_context_registry = get_log_context_registry()
        for context in self.settings.log_config.log_contexts:
            log_context_registry.register_builtin(context)

        log_configurator = get_log_configurator()
        log_configurator.configure()

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            await self.extension_manager.init_all(self._extension_configs)

            self.started_at = time.time()

            yield

            await self.extension_manager.cleanup_all()

        self.app = FastAPI(
            title=self.settings.app_name,
            version=self.settings.app_version,
            docs_url=f"{self.settings.app_context_path}/swagger",
            redoc_url=f"{self.settings.app_context_path}/redoc",
            openapi_url=f"{self.settings.app_context_path}/openapi",
            lifespan=lifespan,
        )

        self.app.state.extension_manager = self.extension_manager

        self._setup_routes()

    def add_extension(self, name: str, extension_class: Type[BaseExtension]) -> None:
        """
        Add an extension to ZeeAPI

        Args:
            name: extension name, will be used as the key of the extension configuration in yaml file,
                  if key not present in yaml file, default parameters will be used if accepted
            extension_class: the type of the extension
        """
        extension = extension_class(self.app)

        self.extension_manager.register(name, extension)

        self._extension_configs[name] = self.settings.model_extra.get(name, {})  # type: ignore[arg-type]

    def _setup_routes(self) -> None:
        """Setup routes"""

        @self.app.get("/healthz", tags=["System"])
        async def healthcheck():
            """Framework health endpoint"""

            uptime = round(time.time() - self.started_at, 2)
            ram = self.current_process.memory_full_info().rss

            return {
                "status": "UP",
                "uptime (seconds)": uptime,
                "app_name": self.settings.app_name,
                "app_version": self.settings.app_version,
                "timestamp": datetime.now().isoformat(),
                "memory usage (mb)": format_bytes(ram),
            }

        @self.app.get("/extensions", tags=["System"])
        async def list_extensions():
            """List all registered extensions"""
            return {"extensions": list(self.extension_manager.extensions.keys())}

    def get_extension(self, name: str) -> BaseExtension:
        """Get extension for use in routes"""
        return self.extension_manager.get(name)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Maintain the default behaviour on uvicorn.run"""
        await self.app(scope, receive, send)
