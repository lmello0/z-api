import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Optional, Type

from fastapi import FastAPI

from zee_api.core.config.settings import Settings
from zee_api.core.extension_manager.base_extension import BaseExtension
from zee_api.core.extension_manager.extension_manager import ExtensionManager
from zee_api.core.logging.context.log_context_registry import get_log_context_registry
from zee_api.core.logging.log_configurator import get_log_configurator

logger = logging.getLogger(__name__)


class ZeeApi:
    def __init__(self) -> None:
        self.settings = Settings()
        self._extension_configs = {}
        self.extension_manager = ExtensionManager()

        log_context_registry = get_log_context_registry()
        for context in self.settings.log_config.log_contexts:
            log_context_registry.register_builtin(context)

        log_configurator = get_log_configurator()
        log_configurator.configure()

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            await self.extension_manager.init_all(self._extension_configs)

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

        self._setup_routes()

    def add_extension(
        self,
        name: str,
        extension_class: Type[BaseExtension],
        config: Optional[dict[str, Any]] = None,
    ) -> None:
        """Add an extension to ZeeAPI"""
        extension = extension_class(self.app)

        self.extension_manager.register(name, extension)

        if config:
            self._extension_configs[name] = config

    def configure(self, config: dict[str, Any]) -> None:
        """Configure all extensions"""
        self._extension_configs.update(config)

    def _setup_routes(self) -> None:
        """Setup routes"""

        @self.app.get("/healthz")
        async def healthcheck():
            """Framework health endpoint"""
            return {"status": "UP", "timestamp": datetime.now().isoformat()}

        @self.app.get("/extensions")
        async def list_extensions():
            """List all registered extensions"""
            return {"extensions": list(self.extension_manager.extensions.keys())}

    def get_extension(self, name: str) -> BaseExtension:
        """Get extension for use in routes"""
        return self.extension_manager.get(name)
