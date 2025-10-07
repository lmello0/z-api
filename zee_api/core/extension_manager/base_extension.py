from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from zee_api.core.zee_api import ZeeApi


class BaseExtension(ABC):
    """Base class for all extensions"""

    def __init__(self, app: "ZeeApi") -> None:
        self.app = app
        self.initialized = False

    @abstractmethod
    async def init(self, config: dict[str, Any]) -> None:
        """Initialize the extension with configuration"""
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup resources when shutting down"""
        pass

    @property
    def name(self) -> str:
        """Return extension name"""
        return self.__class__.__name__
