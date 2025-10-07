import logging
from typing import Any, Optional, Type, TypeVar

from zee_api.core.extension_manager.base_extension import BaseExtension

T = TypeVar("T", bound=BaseExtension)
logger = logging.getLogger(__name__)


class ExtensionManager:
    """Manages all extensions with lifecycle"""

    def __init__(self) -> None:
        self._extensions_by_name: dict[str, BaseExtension] = {}
        self._extensions_by_type: dict[Type[BaseExtension], list[BaseExtension]] = {}

        self._initialized = False

    @property
    def extensions(self) -> dict[str, BaseExtension]:
        """Return all extensions"""
        return self._extensions_by_name.copy()

    def register(self, extension: BaseExtension, name: Optional[str] = None) -> None:
        """Register an extension"""
        if not isinstance(extension, BaseExtension):
            raise TypeError(f"Extension must be an instance of BaseExtension, got {type(extension)}")

        extension_name = name or extension.name
        extension_name = extension_name.lower()

        if extension_name in self._extensions_by_name:
            raise ValueError(f"Extension '{extension_name}' (type: {type(extension)}) already registered")

        self._extensions_by_name[extension_name] = extension

        extension_type = type(extension)
        if extension_type not in self._extensions_by_type:
            self._extensions_by_type[extension_type] = []

        self._extensions_by_type[extension_type].append(extension)

        for base_class in extension_type.mro():
            if issubclass(base_class, BaseExtension) and base_class != BaseExtension:
                if base_class not in self._extensions_by_type:
                    self._extensions_by_type[base_class] = []

                if extension not in self._extensions_by_type[base_class]:
                    self._extensions_by_type[base_class].append(extension)

        logger.info(f"Registered extension: {extension_name} (type: {extension_type.__name__})")

    def get_by_name(self, name: str, default: Optional[Any] = None) -> Optional[BaseExtension]:
        """Get an extension by name, if exists"""
        return self._extensions_by_name.get(name, default)

    def get_by_type(self, extension_type: Type[T]) -> Optional[T]:
        """Get the first extension of the specified type"""
        extensions = self._extensions_by_type.get(extension_type, [])
        return extensions[0] if extensions else None  # type: ignore[return-value]

    def get(self, extension_type: Optional[Type[T]] = None, name: Optional[str] = None) -> Optional[T]:
        """Get an extension by type and/or name (optional)"""
        if name:
            return self.get_by_name(name.lower())  # type: ignore[return-value]

        if extension_type:
            return self.get_by_type(extension_type)

        raise ValueError("'extension_type' or 'name' must be not None")

    def has_extension_name(self, name: str) -> bool:
        """Check if an extension with the given name is registered"""
        return name in self._extensions_by_name

    def has_extension_type(self, extension_type: Type[BaseExtension]) -> bool:
        """Check if any extension of the given type is registered"""
        extensions = self._extensions_by_type.get(extension_type, [])
        return len(extensions) > 0

    async def init_all(self, config: dict[str, Any]) -> None:
        """Initialize all registered extensions"""
        logger.info("Initializing all extensions...")

        for name, extension in self._extensions_by_name.items():
            if extension.initialized:
                continue

            try:
                await extension.init(config.get(name, {}))
                logger.info(f"Extension '{name}' initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize extension '{name}': {e}")
                raise

        self._initialized = True
        logger.info(f"All {len(self._extensions_by_name)} registered extensions was initialized successfully")

    async def cleanup_all(self) -> None:
        """Cleanup all extensions"""
        logger.info("Cleaning up all extensions...")

        cleanup_count = 0
        for name, extension in self._extensions_by_name.items():
            try:
                await extension.cleanup()
                cleanup_count += 1

                logger.info(f"Extension '{name}' cleaned up successfully")
            except Exception as e:
                logger.warning(f"Error cleaning up {name}: {e}")

        logger.info(f"Cleanup complete. {cleanup_count}/{len(self._extensions_by_name)} extensions cleaned up")

    def unregister(self, name: str) -> bool:
        """Unregister an extension by name"""
        if name not in self._extensions_by_name:
            return False

        extension = self._extensions_by_name.pop(name)

        for type_key, extensions_list in self._extensions_by_type.items():
            if extension in extensions_list:
                extensions_list.remove(extension)
                if not extensions_list:
                    del self._extensions_by_type[type_key]

        logger.info(f"Unregistered extension: {name}")
        return True
