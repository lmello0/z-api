import logging

from z_api.core.logging.contexts.response_time_context import get_response_time


class ResponseTimeLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.response_time_ms = get_response_time()
        return True
