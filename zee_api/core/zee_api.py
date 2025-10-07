import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Callable, Optional, Type

import psutil
import uvicorn
from fastapi import FastAPI

from zee_api.core.config.settings import Settings
from zee_api.core.extension_manager.base_extension import BaseExtension
from zee_api.core.extension_manager.extension_manager import ExtensionManager
from zee_api.core.logging.context.log_context_registry import get_log_context_registry
from zee_api.core.logging.log_configurator import get_log_configurator
from zee_api.utils.format_bytes import format_bytes

logger = logging.getLogger(__name__)


class ZeeApi(FastAPI):
    def __init__(self) -> None:
        self.settings = Settings()

        self.extension_manager = ExtensionManager()
        self._extension_configs = {}

        self.current_process = psutil.Process(os.getpid())
        self.started_at: float = float("-inf")

        log_context_registry = get_log_context_registry()
        for context in self.settings.log_config.log_contexts:
            log_context_registry.register_builtin(context)

        log_configurator = get_log_configurator()
        self.log_config = log_configurator.configure()

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            await self.extension_manager.init_all(self._extension_configs)

            self.started_at = time.time()

            yield

            await self.extension_manager.cleanup_all()

        super().__init__(
            title=self.settings.app_name,
            root_path=self.settings.app_context_path,
            version=self.settings.app_version,
            docs_url="/swagger",
            redoc_url="/redoc",
            openapi_url="/openapi",
            lifespan=lifespan,
        )

        self._setup_routes()

    def add_extension(
        self,
        *,
        extension_instance: Optional[BaseExtension] = None,
        extension_class: Optional[Type[BaseExtension]] = None,
        config_key: Optional[str] = None,
        init_early: bool = False,
    ) -> None:
        """
        Add an extension to ZeeAPI

        Args:
            extension_instance: An instantiated extension object
            extension_class: The extension class to instantiate (will receive self as argument)
            config_key: The config key in `application_config.yaml` (defaults to extension.name)
            init_early: If True, initialize the extension immediately (for middlewares, etc.)

        Raises:
            ValueError: If neither or both extension parameters are provided
        """

        if extension_instance is None and extension_class is None:
            raise ValueError("Either 'extension_instance' or 'extension_class' must be provided")

        if extension_instance is not None and extension_class is not None:
            raise ValueError("Provide either 'extension_instance' or 'extension_class', not both")

        if extension_instance is not None:
            extension = extension_instance
        else:
            extension = extension_class(self)  # type: ignore[misc]

        self.extension_manager.register(extension)

        effective_config_key = config_key if config_key is not None else extension.name
        extension_config = self.settings.model_extra.get(effective_config_key, {})  # type: ignore[arg-type]

        self._extension_configs[extension.name.lower()] = extension_config

        if init_early:
            try:
                loop = asyncio.get_running_loop()
                asyncio.create_task(self._init_single_extension(extension, extension_config))
            except RuntimeError:
                asyncio.run(self._init_single_extension(extension, extension_config))

    async def _init_single_extension(self, extension: BaseExtension, config: dict) -> None:
        """Initialize a single extension."""
        logger.info(f"Early initializing extension: {extension.name}")
        await extension.init(config)

    def _setup_routes(self) -> None:
        """Setup routes"""

        @self.get("/healthz", tags=["System"])
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

        @self.get("/extensions", tags=["System"])
        async def list_extensions():
            """List all registered extensions"""
            return {"extensions": list(self.extension_manager.extensions.keys())}

    def get_extension(
        self,
        *,
        extension_type: Optional[Type[BaseExtension]] = None,
        name: Optional[str] = None,
    ) -> Callable:
        """Get extension for use in routes"""
        if not extension_type and not name:
            raise ValueError("'extension_type' or 'name' must be not None")

        def dependency() -> BaseExtension:
            extension = self.extension_manager.get(extension_type, name)

            if not extension:
                if name:
                    raise ValueError(f"Extension '{name}' not found")

                raise ValueError(f"Extension of type '{extension_type}' not found")

            return extension

        return dependency
