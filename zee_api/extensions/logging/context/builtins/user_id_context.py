from fastapi import Request

from zee_api.extensions.logging.context.log_context import LogContext


class UserIdContext(LogContext):
    """User ID context for user tracking."""

    def __init__(self, default_value: str = "anonymous"):
        super().__init__("user_id", default_value=default_value)

    def extract_from_request(self, request: Request) -> str:
        """Extract user_id from request state (set by auth middleware)."""
        return getattr(request.state, "user_id", self.default_value)
