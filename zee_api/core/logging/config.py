import logging
import logging.config
import os
from pathlib import Path
from typing import Optional

import yaml

from zee_api.core.config.settings import Settings
from zee_api.core.exceptions.invalid_config_file_error import (
    InvalidConfigFileError,
)
from zee_api.core.logging.filters.response_time_filter import ResponseTimeLogFilter
from zee_api.core.logging.filters.trace_id_filter import TraceIdLogFilter
from zee_api.utils.deep_merge_dicts import deep_merge_dicts


class LogConfig:
    BASE_LOG_CONFIG = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "[%(asctime)s][%(levelname)s][trace_id: %(trace_id)s][%(name)s]: %(message)s"
            },
            "access": {
                "format": "[%(asctime)s][%(levelname)s][ACCESS][trace_id: %(trace_id)s][response_time_ms: %(response_time_ms)s][%(name)s]: %(message)s"
            },
        },
        "filters": {
            "add_trace_id": {"()": TraceIdLogFilter},
            "response_time_filter": {"()": ResponseTimeLogFilter},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "level": "INFO",
                "filters": ["response_time_filter", "add_trace_id"],
            },
            "access_console": {
                "class": "logging.StreamHandler",
                "formatter": "access",
                "level": "INFO",
                "filters": ["response_time_filter", "add_trace_id"],
            },
        },
        "loggers": {
            "uvicorn": {"level": "INFO", "handlers": ["console"], "propagate": False},
            "uvicorn.error": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            "uvicorn.access": {
                "level": "INFO",
                "handlers": ["access_console"],
                "propagate": False,
            },
        },
        "root": {"level": "INFO", "handlers": ["console"]},
    }

    def __init__(self, settings: Settings):
        self.settings = settings

    def configure(self, *, extra: Optional[dict] = None, apply: bool = True) -> dict:
        """
        Configure the logging, it will merge the base config with the custom, coming from
        `Settings.log_config_path`

        Args:
            extra: A dict that adds custom configurations to the logging
            apply: If True, the logging configuration will be applied immediately

        Returns:
            The current configuration dict
        """
        custom = self._load_custom_config_file(self.settings.log_config_path)
        merged = deep_merge_dicts(self.BASE_LOG_CONFIG, custom)

        if extra:
            merged = deep_merge_dicts(merged, extra)

        merged = self._auto_apply_filters(merged)

        if apply:
            logging.config.dictConfig(merged)
            logging.captureWarnings(True)

        return merged

    def _load_custom_config_file(self, log_path: str) -> dict:
        log_path_abs = Path(log_path).resolve()

        if not os.path.exists(log_path_abs):
            return {}

        with open(log_path_abs, "r") as f:
            config = yaml.safe_load(f)

        if config is not None and not isinstance(config, dict):
            raise InvalidConfigFileError(log_path)

        return config or {}

    def _auto_apply_filters(self, config: dict) -> dict:
        """
        Automatically apply all defined filters to handlers that don't explicitly disable them.

        Handlers can opt-out of auto-applying filters by setting:
        - "auto_filters": false  (disables all auto-filters)
        - "exclude_filters": ["filter_name"]  (excludes specific filters)
        """
        if "filters" not in config or "handlers" not in config:
            return config

        all_filter_names = set(config["filters"].keys())

        for handler_name, handler_config in config["handlers"].items():
            auto_filters = handler_config.pop("auto_filters", True)
            if not auto_filters:
                continue

            excluded = set(handler_config.pop("exclude_filters", []))

            existing_filters = handler_config.get("filters", [])
            if not isinstance(existing_filters, list):
                existing_filters = []

            existing_filters_set = set(existing_filters)

            filters_to_add = all_filter_names - excluded - existing_filters_set

            if filters_to_add or existing_filters:
                handler_config["filters"] = existing_filters + sorted(
                    list(filters_to_add)
                )

        return config
