from typing import Any

from pydantic import BaseModel

from zee_api.extensions.healthchecker.healthstate import HealthState


class ServiceState(BaseModel):
    name: str
    state: HealthState = HealthState.UNKNOWN
    critical: bool
    checked_at: str
    details: dict[Any, Any]
