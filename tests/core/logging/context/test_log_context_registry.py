# tests/test_log_context_registry.py
import importlib
import inspect
import logging
import types
from typing import Any

import pytest
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from zee_api.core.logging.context.log_context import LogContext
from zee_api.core.logging.context.log_context_registry import (
    LogContextRegistry,
    get_log_context_registry,
)


class DummyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        return await call_next(request)


class FakeContext(LogContext):
    """Minimal concrete LogContext used for tests."""

    def __init__(self, tag: str = "fake") -> None:
        self.tag = tag

    def create_filter(self) -> logging.Filter:
        return logging.Filter(name=f"{self.tag}_filter")

    def create_middleware(self) -> type[BaseHTTPMiddleware]:
        return DummyMiddleware

    def extract_from_request(self, request: Request) -> Any:
        return request.headers.get("tag", "null")


@pytest.fixture(autouse=True)
def clear_registry_cache():
    # Ensure the lru_cache doesn't leak between tests
    get_log_context_registry.cache_clear()
    yield
    get_log_context_registry.cache_clear()


def test_register_and_get_and_overwrite():
    reg = LogContextRegistry()

    c1 = FakeContext("alpha")
    c2 = FakeContext("beta")

    reg.register("alpha", c1)
    assert reg.get("alpha") is c1
    assert reg.contexts == {"alpha": c1}

    # Overwrite same key should replace
    reg.register("alpha", c2)
    assert reg.get("alpha") is c2
    assert reg.contexts == {"alpha": c2}

    # Unknown returns None
    assert reg.get("missing") is None


def test_get_all_filters_and_middlewares():
    reg = LogContextRegistry()
    reg.register("c1", FakeContext("one"))
    reg.register("c2", FakeContext("two"))

    filters = reg.get_all_filters()
    assert set(filters.keys()) == {"c1", "c2"}
    assert all(isinstance(f, logging.Filter) for f in filters.values())
    assert filters["c1"].name == "one_filter"
    assert filters["c2"].name == "two_filter"

    middlewares = reg.get_all_middlewares()
    assert set(middlewares.keys()) == {"c1", "c2"}
    assert all(
        inspect.isclass(mw) and issubclass(mw, BaseHTTPMiddleware)
        for mw in middlewares.values()
    )
    assert middlewares["c1"] is DummyMiddleware
    assert middlewares["c2"] is DummyMiddleware


def test_create_filter_config_callable_returns_filter():
    reg = LogContextRegistry()
    a = FakeContext("a")
    b = FakeContext("b")
    reg.register("a", a)
    reg.register("b", b)

    cfg = reg.create_filter_config()
    # Structure: { "a_filter": {"()": <callable>}, ... }
    assert set(cfg.keys()) == {"a_filter", "b_filter"}
    assert callable(cfg["a_filter"]["()"])
    assert callable(cfg["b_filter"]["()"])

    # Call the factory and ensure it returns a logging.Filter
    fa = cfg["a_filter"]["()"]()
    fb = cfg["b_filter"]["()"]()
    assert isinstance(fa, logging.Filter)
    assert isinstance(fb, logging.Filter)
    # Names reflect our FakeContext tag
    assert fa.name == "a_filter"
    assert fb.name == "b_filter"


def test_register_builtin_success(monkeypatch):
    """
    Simulate a builtin module: zee_api.core.logging.context.builtins.<name>_context
    containing exactly one subclass of LogContext.
    """
    # Create a fake module with exactly one LogContext subclass
    mod = types.ModuleType("zee_api.core.logging.context.builtins.request_context")

    class RequestContext(LogContext):
        def __init__(self) -> types.NoneType:
            super().__init__("request", "-")

        def create_filter(self) -> logging.Filter:
            return logging.Filter("request_filter")

        def create_middleware(self) -> type[BaseHTTPMiddleware]:
            return DummyMiddleware

        def extract_from_request(self, request: Request) -> Any:
            pass

    setattr(mod, "RequestContext", RequestContext)

    def fake_import(name):
        if name.endswith(".request_context"):
            return mod
        raise ModuleNotFoundError

    monkeypatch.setattr(importlib, "import_module", fake_import)

    # Wire up the builtins module name like the code expects
    from zee_api.core.logging.context import builtins as builtins_pkg

    # Sanity: ensure we're patching the right path
    assert builtins_pkg.__name__ == "zee_api.core.logging.context.builtins"

    reg = LogContextRegistry()
    reg.register_builtin("request")  # should populate "request": RequestContext()
    ctx = reg.get("request")
    assert isinstance(ctx, RequestContext)
    # And its products behave
    assert isinstance(ctx.create_filter(), logging.Filter)
    assert issubclass(ctx.create_middleware(), BaseHTTPMiddleware)


def test_register_builtin_not_found_raises_value_error(monkeypatch):
    def fake_import(name):
        raise ModuleNotFoundError

    monkeypatch.setattr(importlib, "import_module", fake_import)
    reg = LogContextRegistry()

    with pytest.raises(ValueError) as excinfo:
        reg.register_builtin("nope")
    assert "Builtin 'nope' not found" in str(excinfo.value)


def test_register_builtin_multiple_classes_raises(monkeypatch):
    # Fake module with two LogContext subclasses to trigger the multiple-contexts error
    mod = types.ModuleType("zee_api.core.logging.context.builtins.multi_context")

    class C1(LogContext):
        def create_filter(self):  # type: ignore[override]
            return logging.Filter("c1")

        def create_middleware(self):  # type: ignore[override]
            return DummyMiddleware

    class C2(LogContext):
        def create_filter(self):  # type: ignore[override]
            return logging.Filter("c2")

        def create_middleware(self):  # type: ignore[override]
            return DummyMiddleware

    setattr(mod, "C1", C1)
    setattr(mod, "C2", C2)

    def fake_import(name):
        if name.endswith(".multi_context"):
            return mod
        raise ModuleNotFoundError

    monkeypatch.setattr(importlib, "import_module", fake_import)

    reg = LogContextRegistry()
    with pytest.raises(Exception) as excinfo:
        reg.register_builtin("multi")
    assert "Multiple contexts" in str(excinfo.value)


def test_register_builtin_no_classes_raises(monkeypatch):
    # Module with no LogContext subclasses to trigger "Not found context with this name"
    mod = types.ModuleType("zee_api.core.logging.context.builtins.empty_context")

    class Irrelevant:
        pass

    setattr(mod, "Irrelevant", Irrelevant)

    def fake_import(name):
        if name.endswith(".empty_context"):
            return mod
        raise ModuleNotFoundError

    monkeypatch.setattr(importlib, "import_module", fake_import)

    reg = LogContextRegistry()
    with pytest.raises(Exception) as excinfo:
        reg.register_builtin("empty")
    assert "Not found context with this name" in str(excinfo.value)


def test_get_log_context_registry_is_singleton_via_lru_cache():
    # Same object across calls due to @lru_cache
    r1 = get_log_context_registry()
    r2 = get_log_context_registry()
    assert r1 is r2

    # Clearing the cache should give a new instance
    get_log_context_registry.cache_clear()
    r3 = get_log_context_registry()
    assert r3 is not r1
