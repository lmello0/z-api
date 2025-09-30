import uuid
from typing import Any

from fastapi import Request, Response

from zee_api.core.logging.context.log_context import LogContext


class TraceIdContext(LogContext):
    """Trace ID context for distributed tracing."""

    def __init__(self, header_name: str = "X-Trace-Id"):
        super().__init__("trace_id", default_value="-")
        self.header_name = header_name

    def extract_from_request(self, request: Request) -> Any:
        """Extract trace_id from request headers or generate a new one."""
        return request.headers.get(self.header_name.lower(), str(uuid.uuid4()))

    def prepare_response(self, response: Response, value: Any) -> None:
        response.headers[self.header_name] = value
