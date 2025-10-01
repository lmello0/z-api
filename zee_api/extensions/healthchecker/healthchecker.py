import asyncio
import inspect
import time
from datetime import datetime
from functools import lru_cache
from typing import Any

from zee_api.extensions.healthchecker.service_config import (
    AuthSpec,
    HealthState,
    ServiceConfig,
)
from zee_api.extensions.http.httpx_client import HttpxClient, get_http_client


class Healthchecker:
    def __init__(self, http_client: HttpxClient) -> None:
        self._services = set()
        self._http_client = http_client

        self._results: dict[str, dict[str, Any]] = {}

    @property
    def results(self) -> dict[str, dict[str, Any]]:
        return self._results

    @property
    def services(self) -> list[ServiceConfig]:
        return list(self._services)

    def register_service(self, service: ServiceConfig) -> None:
        self._services.add(service)

    def register_services(self, service_list: list[ServiceConfig]) -> None:
        self._services.update(service_list)

    def overall_readiness(self) -> HealthState:
        if not self._results:
            # TODO: add configuration for user to choose the default behavior
            return HealthState.UP

        if all(r["state"] == HealthState.DOWN for r in self._results.values()):
            return HealthState.DOWN

        if any(
            r["state"] in (HealthState.DOWN, HealthState.DEGRADED)
            for r in self._results.values()
        ):
            return HealthState.DEGRADED

        return HealthState.UP

    async def prime_all(self):
        await asyncio.gather(*(self.probe(svc) for svc in self.services))

    async def probe(self, svc: ServiceConfig):
        started = time.perf_counter()

        # TODO: add configuration for user to choose the default behavior
        state = HealthState.UP
        details = {}

        try:
            if svc.kind == "http":
                url = svc.base_url.rstrip("/") + svc.probe_path  # type: ignore[arg-type]

                headers = {
                    **(svc.extra_headers or {}),
                    **(await self._build_auth_headers(svc.auth)),
                }

                params = svc.request_params or {}

                resp = await self._http_client.request(
                    method=svc.probe_method,
                    url=url,
                    params=params,
                    headers=headers,
                    timeout=svc.timeout_seconds,
                )

                latency_ms = (time.perf_counter() - started) * 1_000

                state = (
                    HealthState.UP
                    if resp.status_code == svc.expected_status
                    else (
                        HealthState.DEGRADED
                        if 200 <= resp.status_code < 500
                        else HealthState.DOWN
                    )
                )

                details = {
                    "status_code": resp.status_code,
                    "latency_ms": round(latency_ms, 1),
                }
        except Exception as e:
            # TODO: add specific exception
            state = HealthState.DOWN
            details = {"error": str(e)}

        self._results[svc.name] = {
            "name": svc.name,
            "state": state,
            "critical": svc.critical,
            "checket_at": str(datetime.now()),
            **details,
        }

    @staticmethod
    async def _build_auth_headers(auth: AuthSpec) -> dict[str, str]:
        if auth.kind == "none":
            return {}

        if auth.kind == "header":
            return {auth.header_name: auth.header_value or ""}

        if auth.kind == "pre-request-func":
            func = auth.pre_request_func

            is_async = inspect.iscoroutine(func)

            args = auth.pre_request_args or []

            if is_async:
                pre_req_data = await func(*args)  # type: ignore[arg-type]
            else:
                pre_req_data = func(*args)  # type: ignore[arg-type]

            if auth.embed_preq_request_data_in == "header":
                return {**{k: str(v) for k, v in pre_req_data.items()}}

        return {}


@lru_cache
def get_healthchecker() -> Healthchecker:
    http_client = get_http_client()

    return Healthchecker(http_client)
