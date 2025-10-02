import logging
import uuid

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from zee_api.core.logging.context.builtins.correlation_id_context import (
    CorrelationIdContext,
)
from zee_api.core.logging.context.log_context import LogContext


def test_extract_from_request_uses_existing_header(monkeypatch):
    ctx = CorrelationIdContext()

    class DummyRequest:
        def __init__(self, headers) -> None:
            self.headers = headers

    req = DummyRequest(headers={"X-Correlation-Id": "abc-123"})

    req.headers["x-correlation-id"] = "abc-123"

    assert ctx.extract_from_request(req) == "abc-123"  # type: ignore[arg-type]


def test_extract_from_request_generates_uuid_when_absent(monkeypatch):
    ctx = CorrelationIdContext()

    fixed = uuid.UUID("12345678-1234-5678-1234-567812345678")
    monkeypatch.setattr(uuid, "uuid4", lambda: fixed)

    class DummyRequest:
        headers = {}

    req = DummyRequest()
    assert ctx.extract_from_request(req) == str(fixed)  # type: ignore[arg-type]


def test_logging_filter_injects_context_value(caplog):
    ctx = CorrelationIdContext()

    logger = logging.getLogger("text_logger_ctx")
    logger.setLevel(logging.DEBUG)

    for h in list(logger.handlers):
        logger.removeHandler(h)
    for f in list(logger.filters):
        logger.removeFilter(f)

    logger.addFilter(ctx.create_filter())

    ctx.set("cid-777")
    with caplog.at_level(logging.INFO, logger=logger.name):
        logger.info("ping")

    assert caplog.records, "expected at least one log record"

    rec = caplog.records[0]
    assert hasattr(rec, "correlation_id")
    assert rec.correlation_id == "cid-777"


@pytest.fixture
def app_with_middleware():
    ctx = CorrelationIdContext()
    AppMiddleware = ctx.create_middleware()

    app = FastAPI()
    app.add_middleware(AppMiddleware)

    @app.get("/echo")
    async def echo(request: Request):
        in_state = getattr(request.state, ctx.context_var_name)
        in_ctx = ctx.get()

        return {"state": in_state, "context": in_ctx}

    app.state._ctx = ctx
    return app


def test_middleware_propagates_existing_id_and_sets_response_header(
    app_with_middleware,
):
    client = TestClient(app_with_middleware)
    ctx: LogContext = app_with_middleware.state._ctx

    assert ctx.get() == ctx.default_value == "-"

    hdr_val = "incoming-123"
    r = client.get("/echo", headers={"X-Correlation-Id": hdr_val})

    assert r.status_code == 200
    data = r.json()

    assert data["state"] == hdr_val
    assert data["context"] == hdr_val

    assert r.headers["X-Correlation-Id"] == hdr_val

    assert ctx.get() == "-"


def test_middleware_generates_when_missing_and_is_unique(
    app_with_middleware, monkeypatch
):
    client = TestClient(app_with_middleware)
    ctx: LogContext = app_with_middleware.state._ctx

    uuids = [
        uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
    ]
    calls = {"i": -1}

    def fake_uuid4():
        calls["i"] += 1
        return uuids[calls["i"]]

    monkeypatch.setattr(uuid, "uuid4", fake_uuid4)

    r1 = client.get("/echo")
    r2 = client.get("/echo")

    assert r1.status_code == 200 and r2.status_code == 200

    d1 = r1.json()
    d2 = r2.json()

    assert d1["state"] == str(uuids[0]) == d1["context"]
    assert d2["state"] == str(uuids[1]) == d2["context"]

    assert r1.headers["X-Correlation-Id"] == str(uuids[0])
    assert r2.headers["X-Correlation-Id"] == str(uuids[1])

    assert ctx.get() == "-"


def test_header_case_insensitivity(app_with_middleware):
    client = TestClient(app_with_middleware)
    hdr_val = "CaseMix-42"

    r = client.get("/echo", headers={"x-coRReLaTiOn-Id": hdr_val})
    assert r.status_code == 200
    data = r.json()

    assert data["state"] == hdr_val
    assert data["context"] == hdr_val
    assert r.headers["X-Correlation-Id"] == hdr_val
