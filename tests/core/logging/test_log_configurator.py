# tests/test_log_configurator.py
import logging
import logging.config
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

import zee_api.core.logging.log_configurator as configurator_module
from zee_api.core.exceptions.invalid_config_file_error import InvalidConfigFileError
from zee_api.core.logging.context.log_context import LogContext
from zee_api.core.logging.log_configurator import (
    LogConfigurator,
    get_log_configurator,
)


class DummyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        return await call_next(request)


class FakeContext(LogContext):
    def __init__(self, tag: str):
        super().__init__("fake", "-")
        self.tag = tag

    def create_filter(self) -> logging.Filter:
        return logging.Filter(name=f"{self.tag}_filter")

    def create_middleware(self):
        return DummyMiddleware

    def extract_from_request(self, request: Request) -> Any:
        pass


class FakeRegistry:
    """Just enough of LogContextRegistry for these tests."""

    def __init__(self, contexts: dict[str, LogContext]):
        self._contexts = contexts

    @property
    def contexts(self):
        return self._contexts


def make_settings_with_log_path(path: str):
    return SimpleNamespace(log_config=SimpleNamespace(log_config_path=path))


@pytest.fixture(autouse=True)
def clear_log_configurator_cache():
    # Ensure lru_cache does not leak across tests
    get_log_configurator.cache_clear()
    yield
    get_log_configurator.cache_clear()


def test_BASE_LOG_CONFIG_builds_filters_and_handlers():
    reg = FakeRegistry(
        {
            "request_id": FakeContext("req"),
            "response_time": FakeContext("rt"),
        }
    )
    settings = make_settings_with_log_path("nonexistent.yaml")
    cfg = LogConfigurator(settings, reg)  # type: ignore[arg-type]

    base = cfg.BASE_LOG_CONFIG

    # Has core structure
    assert base["version"] == 1
    assert "handlers" in base and "filters" in base and "formatters" in base

    assert set(base["filters"].keys()) == {"request_id_filter", "response_time_filter"}
    f_req_factory = base["filters"]["request_id_filter"]["()"]
    f_rt_factory = base["filters"]["response_time_filter"]["()"]
    assert callable(f_req_factory) and callable(f_rt_factory)

    # Factories must produce logging.Filter instances with expected names
    assert isinstance(f_req_factory(), logging.Filter)
    assert isinstance(f_rt_factory(), logging.Filter)

    assert f_req_factory().name == "req_filter"  # type: ignore[arg-type]
    assert f_rt_factory().name == "rt_filter"  # type: ignore[arg-type]


def test_build_format_standard_and_access_including_response_time():
    reg = FakeRegistry(
        {
            "request_id": FakeContext("req"),
            "user": FakeContext("user"),
            "response_time": FakeContext("rt"),
        }
    )
    settings = make_settings_with_log_path("none.yaml")
    cfg = LogConfigurator(settings, reg)  # type: ignore[arg-type]

    std = cfg._build_format("STANDARD")
    acc = cfg._build_format("ACCESS")

    # STANDARD: base + each context + logger name + message
    assert "[%(asctime)s][%(levelname)s]" in std
    assert "[request_id: %(request_id)s]" in std
    assert "[user: %(user)s]" in std
    assert "[response_time: %(response_time)s]" in std
    assert "[%(name)s]: %(message)s" in std
    assert "[ACCESS]" in acc
    assert "[response_time_ms: %(response_time_ms)s]" in acc


def test_build_format_access_without_response_time_special_case():
    # No 'response_time' context -> ACCESS should NOT append response_time_ms piece
    reg = FakeRegistry({"request_id": FakeContext("req")})
    cfg = LogConfigurator(make_settings_with_log_path("none.yaml"), reg)  # type: ignore[arg-type]

    acc = cfg._build_format("ACCESS")
    assert "[ACCESS]" in acc
    assert "[response_time_ms:" not in acc


def test_load_custom_config_file_nonexistent_returns_empty(tmp_path: Path):
    cfg = LogConfigurator(
        make_settings_with_log_path(str(tmp_path / "nope.yml")), FakeRegistry({})  # type: ignore[arg-type]
    )
    out = cfg._load_custom_config_file(str(tmp_path / "nope.yml"))
    assert out == {}


def test_load_custom_config_file_valid_yaml_dict(tmp_path: Path):
    p = tmp_path / "log.yml"
    payload = {"handlers": {"h": {"class": "logging.StreamHandler"}}}
    p.write_text(yaml.safe_dump(payload))
    cfg = LogConfigurator(make_settings_with_log_path(str(p)), FakeRegistry({}))  # type: ignore[arg-type]
    out = cfg._load_custom_config_file(str(p))
    assert out == payload


def test_load_custom_config_file_invalid_yaml_type_raises(tmp_path: Path):
    p = tmp_path / "log.yml"
    p.write_text(yaml.safe_dump(["not", "a", "dict"]))
    cfg = LogConfigurator(make_settings_with_log_path(str(p)), FakeRegistry({}))  # type: ignore[arg-type]
    with pytest.raises(InvalidConfigFileError):
        cfg._load_custom_config_file(str(p))


def test_auto_apply_filters_default_adds_all_sorted():
    base = {
        "filters": {
            "a": {"()": object()},
            "b": {"()": object()},
            "c": {"()": object()},
        },
        "handlers": {
            "console": {"class": "logging.StreamHandler"}
        },  # no filters -> should add all
    }
    cfg = LogConfigurator(make_settings_with_log_path("none.yaml"), FakeRegistry({}))  # type: ignore[arg-type]
    out = cfg._auto_apply_filters(base)
    assert out["handlers"]["console"]["filters"] == ["a", "b", "c"]  # sorted insertion


def test_auto_apply_filters_respects_exclude_and_existing_and_optout():
    base = {
        "filters": {"a": {}, "b": {}, "c": {}},
        "handlers": {
            # Default auto -> add all except excluded
            "h1": {"class": "X", "exclude_filters": ["b"]},
            # Explicit existing list merged with the rest
            "h2": {"class": "X", "filters": ["a"]},
            # Opt-out entirely
            "h3": {"class": "X", "auto_filters": False},
        },
    }
    cfg = LogConfigurator(make_settings_with_log_path("none.yaml"), FakeRegistry({}))  # type: ignore[arg-type]
    out = cfg._auto_apply_filters(base)

    # h1 gets all filters minus excluded, sorted
    assert out["handlers"]["h1"]["filters"] == ["a", "c"]
    # h2 keeps 'a' and adds the missing others sorted without duplicates
    assert out["handlers"]["h2"]["filters"] == ["a", "b", "c"]
    # h3 gets no auto-applied filters and no 'filters' key is forced
    assert "filters" not in out["handlers"]["h3"]


def test_configure_merges_base_custom_and_extra_and_applies(
    monkeypatch, tmp_path: Path
):
    # Registry with one context to ensure a filter/format exists
    reg = FakeRegistry({"request_id": FakeContext("req")})

    # Custom file adds a handler and tweaks levels
    custom_dict = {
        "handlers": {
            "file": {
                "class": "logging.StreamHandler",
                "level": "WARNING",
                "formatter": "standard",
            }
        },
        "root": {"level": "WARNING", "handlers": ["console", "file"]},
    }
    p = tmp_path / "logging.yml"
    p.write_text(yaml.safe_dump(custom_dict))

    settings = make_settings_with_log_path(str(p))
    cfg = LogConfigurator(settings, reg)  # type: ignore[arg-type]

    applied = {}

    def fake_dict_config(d):
        applied["config"] = d

    captured = {}

    def fake_capture_warnings(flag):
        captured["flag"] = flag

    monkeypatch.setattr(logging.config, "dictConfig", fake_dict_config)
    monkeypatch.setattr(logging, "captureWarnings", fake_capture_warnings)

    extra = {"loggers": {"uvicorn": {"level": "DEBUG"}}}
    merged = cfg.configure(extra=extra, apply=True)

    # dictConfig and captureWarnings(True) must have been called
    assert applied["config"] == merged
    assert captured["flag"] is True

    # Ensure merge happened: custom handler present and extra logger level set
    assert "file" in merged["handlers"]
    assert merged["root"]["level"] == "WARNING"
    assert merged["loggers"]["uvicorn"]["level"] == "DEBUG"

    # Auto-applied filters should appear on handlers (console at least)
    assert "filters" in merged["handlers"]["console"]
    # Filter key derived from context name
    assert any(f.endswith("_filter") for f in merged["handlers"]["console"]["filters"])


def test_configure_apply_false_does_not_call_logging(monkeypatch, tmp_path: Path):
    reg = FakeRegistry({"request_id": FakeContext("req")})
    p = tmp_path / "empty.yml"
    p.write_text(yaml.safe_dump({}))
    cfg = LogConfigurator(make_settings_with_log_path(str(p)), reg)  # type: ignore[arg-type]

    called = {"dict": 0, "warn": 0}
    monkeypatch.setattr(
        logging.config, "dictConfig", lambda d: called.__setitem__("dict", 1)
    )
    monkeypatch.setattr(
        logging, "captureWarnings", lambda f: called.__setitem__("warn", 1)
    )

    cfg.configure(apply=False)
    assert called["dict"] == 0
    assert called["warn"] == 0


def test_get_log_configurator_is_singleton_and_uses_injected_deps(monkeypatch):
    # Prepare fake settings + registry to be returned by the module-level factories
    fake_settings = make_settings_with_log_path("nope.yml")
    fake_registry = FakeRegistry({"user": FakeContext("user")})

    # Monkeypatch the module-level functions used inside get_log_configurator()
    monkeypatch.setattr(configurator_module, "get_app_settings", lambda: fake_settings)
    monkeypatch.setattr(
        configurator_module, "get_log_context_registry", lambda: fake_registry
    )

    # First call builds it
    c1 = get_log_configurator()
    # Second call returns the same instance due to lru_cache
    c2 = get_log_configurator()
    assert c1 is c2
    assert isinstance(c1, LogConfigurator)
    # And it wired our fakes
    assert c1.settings is fake_settings
    assert c1.context_registry is fake_registry

    # Clearing cache yields a new instance
    get_log_configurator.cache_clear()
    c3 = get_log_configurator()
    assert c3 is not c1


class TrapDict(dict):
    def __init__(self, present_keys=()):
        super().__init__()
        self._present = set(present_keys)

    def __contains__(self, key: object) -> bool:
        return key in self._present

    def __getitem__(self, key: Any) -> Any:
        raise AssertionError(f"Should not access config['{key}'] when early-returning")


def test_auto_apply_filters_without_filters():
    config = TrapDict(present_keys={"filters"})

    fake_registry = FakeRegistry({})
    cfg = LogConfigurator(make_settings_with_log_path("none.yaml"), fake_registry)  # type: ignore[arg-type]

    out = cfg._auto_apply_filters(config)

    assert out is config


def test_auto_apply_filters_without_handlers():
    config = TrapDict(present_keys={"handlers"})

    fake_registry = FakeRegistry({})
    cfg = LogConfigurator(make_settings_with_log_path("none.yaml"), fake_registry)  # type: ignore[arg-type]

    out = cfg._auto_apply_filters(config)

    assert out is config


def test_auto_apply_filters_existing_filters_not_list():
    config = {
        "filters": {},
        "handlers": {
            "file": {
                "class": "logging.StreamHandler",
                "level": "WARNING",
                "formatter": "standard",
                "filters": "not a list",
            }
        },
    }

    fake_registry = FakeRegistry({})
    cfg = LogConfigurator(make_settings_with_log_path("none.yaml"), fake_registry)  # type: ignore[arg-type]

    new_config = cfg._auto_apply_filters(config)

    assert new_config["handlers"]["file"].get("filters") != "not a list"
    assert isinstance(new_config["handlers"]["file"]["filters"], list)
