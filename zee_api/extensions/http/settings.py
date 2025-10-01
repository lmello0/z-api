from typing import Literal

from pydantic import BaseModel


class TimeoutSettings(BaseModel):
    timeout_op: int = 10
    timeout_connect: int = 5


class WaitSettings(BaseModel):
    policy: Literal[
        "exponential",
        "exponential_jitter",
        "fixed",
        "incrementing",
        "random",
        "random_exponential",
    ] = "exponential"
    exp_base: float = 2.0
    initial: float = 0.5
    max: float = 4.0
    jitter: bool = True
    fixed_wait: float = 1.0
    increment_start: float = 1.0
    increment_step: float = 0.5


class HttpSettings(BaseModel):
    verify_ssl: bool = False
    max_connections: int = 100
    max_keepalive_connections: int = 20
    default_retry_attempts: int = 3
    semaphore_size: int = 150
    follow_redirects: bool = True
    timeout: TimeoutSettings = TimeoutSettings()
    wait: WaitSettings = WaitSettings()
