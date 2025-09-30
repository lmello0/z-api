import uuid

from fastapi import Request, Response

from zee_api.core.logging.context.log_context import LogContext


class CorrelationIdContext(LogContext):
    """Correlation ID for tracking related requests."""

    def __init__(self):
        super().__init__("correlation_id", default_value="-")

    def extract_from_request(self, request: Request) -> str:
        """Extract correlation_id from headers or generate new one."""
        return request.headers.get("x-correlation-id", str(uuid.uuid4()))

    def prepare_response(self, response: Response, value: str) -> None:
        """Add correlation_id to response headers."""
        response.headers["X-Correlation-Id"] = value
