from typing import Literal, Optional

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

from zee_api.extensions.healthchecker.healthstate import HealthState


class ServiceAuthSettings(BaseModel, frozen=True):
    kind: Literal["none", "header"] = "none"

    # header auth
    header_name: str = "X-API-KEY"
    header_value: Optional[str] = None


class ServiceSettings(BaseModel, frozen=True):
    name: str
    kind: Literal["http"] = "http"

    # http
    base_url: str
    probe_method: Literal[
        "GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"
    ] = "GET"
    probe_path: str = "/health"
    expected_status: int = 200
    extra_headers: Optional[dict[str, str]] = None

    # general
    critical: bool = True
    timeout_seconds: float = 30.0
    auth: ServiceAuthSettings = ServiceAuthSettings()
    request_params: Optional[dict[str, str]] = None


class HealthcheckerSettings(BaseSettings):
    check_interval_seconds: int = 15
    default_status: Literal[
        HealthState.UP, HealthState.DOWN, HealthState.DEGRADED, HealthState.UNKNOWN
    ] = HealthState.UP
    services_config: list[ServiceSettings] = []

    model_config = SettingsConfigDict(frozen=True, extra="ignore")
