import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from zee_api.core.logging.contexts.response_time_context import set_response_time


class ResponseTimeMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start_time = time.perf_counter()

        response = await call_next(request)

        end_time = time.perf_counter()

        response_time_ms = int((end_time - start_time) * 1_000)

        set_response_time(str(response_time_ms))

        return response
