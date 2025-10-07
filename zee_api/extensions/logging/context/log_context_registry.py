import importlib
import inspect
import logging
from functools import lru_cache
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware

from zee_api.extensions.logging.context import builtins
from zee_api.extensions.logging.context.log_context import LogContext


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

    def register_builtin(self, context_name: str) -> None:
        """Register a builtin log context"""

        try:
            mod = importlib.import_module(f"{builtins.__name__}.{context_name}_context")

            contexts = [
                c
                for _, c in inspect.getmembers(mod, inspect.isclass)
                if issubclass(c, LogContext) and c is not LogContext
            ]

            if not contexts:
                # TODO: add specific exception
                raise Exception("Not found context with this name")

            if len(contexts) > 1:
                # TODO: add specific exception
                raise Exception("Multiple contexts found with this name")

            context = contexts[0]
            self.register(context_name, context())  # type: ignore[arg-type]

        except ModuleNotFoundError:
            raise ValueError(f"Builtin '{context_name}' not found")

    def get(self, name: str) -> Optional[LogContext]:
        """Get a registered context by name."""
        return self._contexts.get(name)

    def get_all_filters(self) -> dict[str, logging.Filter]:
        """Get all filter classes from registered contexts."""
        return {name: context.create_filter() for name, context in self._contexts.items()}

    def get_all_middlewares(self) -> dict[str, type[BaseHTTPMiddleware]]:
        """Get all middleware classes from registered contexts."""
        return {name: context.create_middleware() for name, context in self._contexts.items()}

    def create_filter_config(self) -> dict:
        """Create filter configuration for `logging.yaml`"""
        return {f"{name}_filter": {"()": lambda ctx=ctx: ctx.create_filter()} for name, ctx in self._contexts.items()}


@lru_cache
def get_log_context_registry() -> LogContextRegistry:
    return LogContextRegistry()
