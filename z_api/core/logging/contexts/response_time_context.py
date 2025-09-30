from contextvars import ContextVar

_RESPONSE_TIME: ContextVar[str] = ContextVar("response_time_ms", default="-")


def set_response_time(response_time: str) -> None:
    _RESPONSE_TIME.set(response_time)


def get_response_time() -> str:
    return _RESPONSE_TIME.get()
