import logging
from abc import ABC, abstractmethod
from contextvars import ContextVar
from typing import Any, Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class LogContext(ABC):
    """Base class for log context providers"""

    def __init__(self, context_var_name: str, default_value: Any = "-") -> None:
        self.context_var: ContextVar = ContextVar(
            context_var_name, default=default_value
        )
        self.context_var_name = context_var_name
        self.default_value = default_value

    def set(self, value: Any) -> None:
        """Set the context value"""
        self.context_var.set(value)

    def get(self) -> Any:
        """Get the context value"""
        return self.context_var.get()

    def reset(self) -> None:
        """Reset to default value"""
        self.context_var.set(self.default_value)

    @abstractmethod
    def extract_from_request(self, request: Request) -> Any:
        """Extract the context value from the request."""
        pass

    def prepare_response(self, response: Response, value: Any) -> None:
        """Optionally add the context value to the response headers."""
        pass

    def create_filter(self) -> logging.Filter:
        """Create a logging filter for this context."""
        context = self

        class ContextLogFilter(logging.Filter):
            def filter(self, record: logging.LogRecord) -> bool:
                setattr(record, context.context_var_name, context.get())
                return True

        return ContextLogFilter()

    def create_middleware(self) -> type[BaseHTTPMiddleware]:
        """Create a middleware class for this context."""
        context = self

        class ContextMiddleware(BaseHTTPMiddleware):
            async def dispatch(
                self,
                request: Request,
                call_next: Callable[[Request], Awaitable[Response]],
            ) -> Response:
                value = context.extract_from_request(request)

                setattr(request.state, context.context_var_name, value)
                context.set(value)

                response = await call_next(request)

                context.prepare_response(response, value)

                context.reset()

                return response

        return ContextMiddleware
