import uuid

from fastapi import Request, Response

from zee_api.core.logging.context.log_context import LogContext


class RequestIdContext(LogContext):
    """Request ID context for request tracking."""

    def __init__(self):
        super().__init__("request_id", default_value="-")

    def extract_from_request(self, request: Request) -> str:
        """Generate a unique request ID."""
        return request.headers.get("x-request-id", str(uuid.uuid4()))

    def prepare_response(self, response: Response, value: str) -> None:
        """Add request_id to response headers."""
        response.headers["X-Request-Id"] = value
