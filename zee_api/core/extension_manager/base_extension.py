from abc import ABC, abstractmethod
from typing import Any

from fastapi import FastAPI


class BaseExtension(ABC):
    """Base class for all extensions"""

    def __init__(self, app: FastAPI) -> None:
        self.app = app
        self._initialized = False

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
