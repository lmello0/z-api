import logging
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware

from zee_api.core.logging.context.log_context import LogContext


class LogContextRegistry:
    """Central registry for managing all log contexts."""

    def __init__(self) -> None:
        self._contexts: dict[str, LogContext] = {}

    @property
    def contexts(self) -> dict[str, LogContext]:
        """Get all registered contexts"""
        return self._contexts

    def register(self, name: str, context: LogContext) -> None:
        """Register a new log context."""
        self._contexts[name] = context

    def get(self, name: str) -> Optional[LogContext]:
        """Get a registered context by name."""
        return self._contexts.get(name)

    def get_all_filters(self) -> dict[str, logging.Filter]:
        """Get all filter classes from registered contexts."""
        return {
            name: context.create_filter() for name, context in self._contexts.items()
        }

    def get_all_middlewares(self) -> dict[str, type[BaseHTTPMiddleware]]:
        """Get all middleware classes from registered contexts."""
        return {
            name: context.create_middleware()
            for name, context in self._contexts.items()
        }

    def create_filter_config(self) -> dict:
        """Create filter configuration for `logging.yaml`"""
        return {
            f"{name}_filter": {"()": lambda ctx=ctx: ctx.create_filter()}
            for name, ctx in self._contexts.items()
        }
