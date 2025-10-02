import os
import textwrap
from pathlib import Path

import pytest
from pydantic_core import ValidationError

from zee_api.core.config.settings import LogConfig, Settings, get_app_settings


def test_settings_customize_sources_uses_only_yaml_source():
    sources = Settings.settings_customise_sources(Settings, None, None, None, None)  # type: ignore[arg-type]

    assert isinstance(sources, tuple) and len(sources) == 3
    assert sources[2].__class__.__name__ == "SpringYamlSettingsSource"


def test_defaults_without_yaml_file(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    s = Settings()

    assert s.app_name == "Zee-API"
    assert s.app_version == "0.1.0"
    assert s.app_env == "dev"
    assert s.app_context_path == "/zee-api"
    assert isinstance(s.log_config, LogConfig)
    assert hasattr(s, "http_config")


def test_yaml_values_are_applied_and_extra_allowed(monkeypatch, tmp_path: Path):
    resources = tmp_path / "resources"
    resources.mkdir(parents=True)

    cfg_path = resources / "application_config.yaml"

    cfg_path.write_text(
        textwrap.dedent(
            """
            app_name: "Zeebra API"
            app_version: "9.9.9"
            app_env: "prod"
            app_context_path: "/zprod"
            log_config:
                log_level: "DEBUG"
                log_config_path: "resources/custom_logging.yaml"
                log_contexts: ["request_id"]

            some_extra_flag: true
            """
        )
    )

    monkeypatch.chdir(tmp_path)
    s = Settings()

    assert s.app_name == "Zeebra API"
    assert s.app_version == "9.9.9"
    assert s.app_env == "prod"
    assert s.app_context_path == "/zprod"

    assert isinstance(s.log_config, LogConfig)
    assert s.log_config.log_level == "DEBUG"
    assert s.log_config.log_config_path == "resources/custom_logging.yaml"
    assert s.log_config.log_contexts == ["request_id"]

    assert getattr(s, "some_extra_flag", None) is True
    assert "some_extra_flag" in (s.model_extra or {})


def test_model_is_frozen(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)

    (tmp_path / "resources").mkdir(parents=True)
    (tmp_path / "resources" / "application_config.yaml").write_text("")

    s = Settings()
    with pytest.raises(ValidationError):
        s.app_name = "new-name"

    with pytest.raises(ValidationError):
        s.log_config.log_level = "TRACE"


def test_get_app_settings_is_cached(monkeypatch, tmp_path: Path):
    get_app_settings.cache_clear()

    resources = tmp_path / "resources"
    resources.mkdir(parents=True)
    (resources / "application_config.yaml").write_text('app_name: "Cached App"\n')

    monkeypatch.chdir(tmp_path)

    s1 = get_app_settings()
    s2 = get_app_settings()

    assert s1 is s2
    assert s1.app_name == "Cached App"

    (resources / "application_config.yaml").write_text('app_name: "Changed"\n')
    s3 = get_app_settings()

    assert s3.app_name == "Cached App"

    get_app_settings.cache_clear()
    s4 = get_app_settings()

    assert s4 is not s1
    assert s4.app_name == "Changed"


def test_env_vars_settings(monkeypatch, tmp_path: Path):
    resources = tmp_path / "resources"
    resources.mkdir(parents=True)

    cfg_path = resources / "application_config.yaml"

    cfg_path.write_text(
        textwrap.dedent(
            """
            app_name: ${APP_NAME:Zee-API}
            app_version: ${APP_VERSION}
            app_env: ${APP_ENV}
            """
        )
    )

    os.environ["APP_ENV"] = "test"

    monkeypatch.chdir(tmp_path)
    s = Settings()

    assert s.app_name == "Zee-API"
    assert not s.app_version
    assert s.app_env == "test"
