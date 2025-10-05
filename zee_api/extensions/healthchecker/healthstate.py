from enum import StrEnum


class HealthState(StrEnum):
    UNKNOWN = "UNKNOWN"
    UP = "UP"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"
