import asyncio
import time
from datetime import datetime
from typing import Any, Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from zee_api.core.extension_manager.base_extension import BaseExtension
from zee_api.extensions.healthchecker.healthstate import HealthState
from zee_api.extensions.healthchecker.service_state import ServiceState
from zee_api.extensions.healthchecker.settings import (
    HealthcheckerSettings,
    ServiceAuthSettings,
    ServiceSettings,
)
from zee_api.extensions.http.httpx_client import HttpxClient


class Healthchecker(BaseExtension):
    def __init__(self, app: FastAPI) -> None:
        super().__init__(app)
        self._http_client: Optional[HttpxClient] = None
        self.config: Optional[HealthcheckerSettings] = None

        self._services: set[ServiceSettings] = set()
        self._results: dict[str, ServiceState] = {}

    async def init(self, config: dict[str, Any]) -> None:
        """Initialize Healthchecker"""
        self.settings = HealthcheckerSettings(**config)

        if not getattr(self.app.state, "extension_manager"):
            raise ValueError("Application does not have a ExtensionManager registered")

        try:
            self._http_client = self.app.state.extension_manager.get("http_client")
        except KeyError:
            raise ValueError(
                "Application does not have a HttpClient extension registered, healthchecker cannot be used"
            )

        for service in self.settings.services_config:
            self._services.add(service)
            self._results[service.name] = ServiceState(
                name=service.name,
                state=HealthState.UNKNOWN,
                critical=service.critical,
                checked_at=str(datetime.now()),
                details={},
            )

        self._setup_routes()

        self._initialized = True

    async def cleanup(self):
        """Shutdown healthchecker"""
        if self._http_client:
            self._http_client = None

        self._services.clear()
        self._results.clear()

    @property
    def results(self) -> dict[str, ServiceState]:
        return self._results

    @property
    def services(self) -> list[ServiceSettings]:
        return list(self._services)

    def register_service(self, service: ServiceSettings) -> None:
        self._services.add(service)

    def register_services(self, service_list: list[ServiceSettings]) -> None:
        self._services.update(service_list)

    def overall_readiness(self) -> HealthState:
        if not self._results:
            return self.settings.default_status

        if all(r.state == HealthState.DOWN for r in self._results.values()):
            return HealthState.DOWN

        if any(
            r.state in (HealthState.DOWN, HealthState.DEGRADED)
            for r in self._results.values()
        ):
            return HealthState.DEGRADED

        return HealthState.UP

    async def prime_all(self):
        await asyncio.gather(*(self.probe(svc) for svc in self.services))

    async def probe(self, svc: ServiceSettings):
        started = time.perf_counter()

        state = self.settings.default_status
        details = {}

        try:
            if svc.kind == "http":
                url = svc.base_url.rstrip("/") + svc.probe_path  # type: ignore[arg-type]

                headers = {
                    **(svc.extra_headers or {}),
                    **(await self._build_auth_headers(svc.auth)),
                }

                params = svc.request_params or {}

                if not self._http_client:
                    raise ValueError("HTTP Client is None")

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
            state = HealthState.DOWN
            details = {"error": str(e)}

        self._results[svc.name] = ServiceState(
            name=svc.name,
            state=state,
            critical=svc.critical,
            checked_at=str(datetime.now()),
            details=details,
        )

    def _setup_routes(self) -> None:
        @self.app.get("/readyz", tags=["Healthchecker"])
        async def readyz():
            overall = self.overall_readiness()
            return JSONResponse(
                status_code=200 if overall == HealthState.UP else 503,
                content={
                    "overall_status": overall,
                    "downstreams": {k: v.model_dump() for k, v in self.results.items()},
                },
            )

    @staticmethod
    async def _build_auth_headers(auth: ServiceAuthSettings) -> dict[str, str]:
        if auth.kind == "none":
            return {}

        if auth.kind == "header":
            return {auth.header_name: auth.header_value or ""}

        return {}
