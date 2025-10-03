import logging
from typing import Any

from zee_api.core.extension_manager.base_extension import BaseExtension

logger = logging.getLogger(__name__)


class ExtensionManager:
    """Manages all extensions with lifecycle"""

    def __init__(self):
        self._extensions: dict[str, BaseExtension] = {}
        self._initialized = False

    @property
    def extensions(self) -> dict[str, BaseExtension]:
        """Return all extensions"""
        return self._extensions

    def register(self, name: str, extension: BaseExtension) -> None:
        """Register an extension"""
        if name in self._extensions:
            raise ValueError(f"Extension '{name}' already registered")

        self._extensions[name] = extension
        logger.info(f"Registered extension: {name}")

    def get(self, name: str) -> BaseExtension:
        """Get an extension by name"""
        if name not in self._extensions:
            raise KeyError(f"Extension '{name}' not found")

        return self._extensions[name]

    async def init_all(self, config: dict[str, Any]) -> None:
        """Initialize all registered extensions"""
        logger.info("Initializing all extensions...")

        for name, extension in self._extensions.items():
            await extension.init(config.get(name) or {})
            logger.info(f"Extension '{name}' initialized successfully")

        self._initialized = True
        logger.info(
            f"All {len(self._extensions)} registered extensions initialized successfully"
        )

    async def cleanup_all(self) -> None:
        """Cleanup all extensions"""
        logger.info("Cleaning up all extensions...")
        for name, extension in self._extensions.items():
            try:
                await extension.cleanup()
            except Exception as e:
                logger.info(f"Error cleaning up {name}: {e}")

        logger.info(
            f"Cleanup complete. Cleanup ran for {len(self._extensions)} extensions"
        )

    def __getitem__(self, name: str) -> BaseExtension:
        """Allow dictionary-style access"""
        return self.get(name)
