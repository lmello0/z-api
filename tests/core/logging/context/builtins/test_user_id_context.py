import logging

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from zee_api.core.logging.context.builtins.user_id_context import (
    UserIdContext,
)
from zee_api.core.logging.context.log_context import LogContext


def test_extract_from_request_reads_state_user_id(monkeypatch):
    ctx = UserIdContext()

    class DummyState:
        pass

    class DummyRequest:
        def __init__(self):
            self.state = DummyState()

    req = DummyRequest()
    req.state.user_id = "user-42"  # type: ignore[arg-type]

    assert ctx.extract_from_request(req) == "user-42"  # type: ignore[arg-type]


def test_extract_from_request_returns_default_when_missing():
    ctx = UserIdContext()

    class DummyState:
        pass

    class DummyRequest:
        def __init__(self):
            self.state = DummyState()

    req = DummyRequest()

    assert ctx.extract_from_request(req) == "anonymous"  # type: ignore[arg-type]


def test_extract_from_request_respects_custom_default():
    ctx = UserIdContext(default_value="guest")

    class DummyState:
        pass

    class DummyRequest:
        def __init__(self):
            self.state = DummyState()

    req = DummyRequest()
    assert ctx.extract_from_request(req) == "guest"  # type: ignore[arg-type]


def test_logging_filter_injects_context_value(caplog):
    ctx = UserIdContext()

    logger = logging.getLogger("text_logger_ctx")
    logger.setLevel(logging.DEBUG)

    for h in list(logger.handlers):
        logger.removeHandler(h)
    for f in list(logger.filters):
        logger.removeFilter(f)

    logger.addFilter(ctx.create_filter())

    ctx.set("user-abc")
    with caplog.at_level(logging.INFO, logger=logger.name):
        logger.info("ping")

    assert caplog.records, "expected at least one log record"

    rec = caplog.records[0]
    assert hasattr(rec, "user_id")
    assert rec.user_id == "user-abc"


class FakeAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, user_id=None):
        super().__init__(app)
        self._user_id = user_id

    async def dispatch(self, request: Request, call_next) -> Response:
        if self._user_id is not None:
            setattr(request.state, "user_id", self._user_id)

        return await call_next(request)


def build_app_with_user_ctx(default_value="anonymous", auth_user_id=None):
    ctx = UserIdContext(default_value=default_value)
    UserCtxMiddleware = ctx.create_middleware()

    app = FastAPI()

    app.add_middleware(UserCtxMiddleware)
    app.add_middleware(FakeAuthMiddleware, user_id=auth_user_id)

    @app.get("/whoami")
    async def whoami(request: Request):
        return {"state": getattr(request.state, "user_id", None), "context": ctx.get()}

    app.state._ctx = ctx
    return app


def test_middleware_uses_state_user_id_and_resets_after():
    app = build_app_with_user_ctx(auth_user_id="auth-123")
    client = TestClient(app)

    ctx: LogContext = app.state._ctx

    assert ctx.get() == "anonymous"

    r = client.get("/whoami")
    assert r.status_code == 200

    data = r.json()

    assert data["state"] == "auth-123"
    assert data["context"] == "auth-123"

    assert ctx.get() == "anonymous"


def test_middleware_sets_default_when_no_auth_and_resets():
    app = build_app_with_user_ctx()
    client = TestClient(app)
    ctx: LogContext = app.state._ctx

    r = client.get("/whoami")
    assert r.status_code == 200
    data = r.json()

    # Our middleware should set request.state.user_id to the default
    assert data["state"] == "anonymous"
    assert data["context"] == "anonymous"

    # Context resets after the request
    assert ctx.get() == "anonymous"


def test_middleware_respects_custom_default_when_absent():
    app = build_app_with_user_ctx(default_value="guest", auth_user_id=None)
    client = TestClient(app)
    ctx: LogContext = app.state._ctx  # type: ignore

    r = client.get("/whoami")
    assert r.status_code == 200
    data = r.json()

    assert data["state"] == "guest"
    assert data["context"] == "guest"
    assert ctx.get() == "guest"  # reset to custom default
