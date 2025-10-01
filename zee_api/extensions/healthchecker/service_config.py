from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable, Coroutine, Literal, Optional


class HealthState(StrEnum):
    UP = "UP"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"


@dataclass(frozen=True)
class AuthSpec:
    kind: Literal["none", "header", "pre-request-func"] = "none"

    # header auth
    header_name: str = "X-API-KEY"
    header_value: Optional[str] = None
    pre_request_func: Optional[
        Callable[[Any], dict[str, str]] | Coroutine[Any, Any, dict[str, str]]
    ] = None
    pre_request_args: Optional[list[Any]] = None
    embed_preq_request_data_in: Literal["none", "header"] = "none"

    def __post_init__(self):
        if self.kind == "pre-request-func" and self.pre_request_func is None:
            raise ValueError(
                "'pre_request_func' must be provided when kind is 'pre-request'"
            )


@dataclass(frozen=True)
class ServiceConfig:
    name: str
    kind: Literal["http", "tcp"] = "http"
    # http
    base_url: Optional[str] = None
    probe_method: Literal[
        "GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"
    ] = "GET"
    probe_path: str = "/health"
    expected_status: int = 200
    extra_headers: Optional[dict[str, str]] = None
    # genral
    critical: bool = True
    timeout_seconds: float = 30.0
    auth: AuthSpec = AuthSpec()
    request_params: Optional[dict[str, str]] = None

    def __post_init__(self):
        if self.kind == "http" and self.base_url is None:
            raise ValueError("'base_url' must be not None if probe is http")
