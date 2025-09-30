import logging

from zee_api.core.logging.contexts.trace_id_context import get_trace_id


class TraceIdLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = get_trace_id()
        return True
