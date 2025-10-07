import logging
import logging.config
import os
from pathlib import Path
from typing import Any, Literal, Optional

import yaml

from zee_api.core.exceptions.invalid_config_file_error import (
    InvalidConfigFileError,
)
from zee_api.core.extension_manager.base_extension import BaseExtension
from zee_api.core.zee_api import ZeeApi
from zee_api.extensions.logging.context.log_context_registry import LogContextRegistry
from zee_api.extensions.logging.settings import LoggingModuleSettings
from zee_api.utils.deep_merge_dicts import deep_merge_dicts


class LogConfigurator(BaseExtension):
    def __init__(self, app: ZeeApi) -> None:
        super().__init__(app)
        self._context_registry: LogContextRegistry = LogContextRegistry()

        self.config: Optional[LoggingModuleSettings] = None

        self._base_config: Optional[dict[str, Any]] = None

    async def init(self, config: dict[str, Any]) -> None:
        self.config = LoggingModuleSettings(**config)

        for context in self.config.log_contexts:
            self._context_registry.register_builtin(context)

        self.configure()

        for _, context in self._context_registry.contexts.items():
            self.app.add_middleware(context.create_middleware())

        self.initialized = True

    async def cleanup(self) -> None:
        pass

    @property
    def BASE_LOG_CONFIG(self) -> dict:
        """Generate base config dynamically with registered contexts."""
        if not self._context_registry:
            raise ValueError("LogConfigurator is not initialized yet")

        if self._base_config is None:
            context_filters = {}
            for name, context in self._context_registry.contexts.items():
                filter_instance = context.create_filter()
                context_filters[f"{name}_filter"] = {"()": lambda f=filter_instance: f}

            self._base_config = {
                "version": 1,
                "disable_existing_loggers": False,
                "formatters": {
                    "standard": {"format": self._build_format("STANDARD")},
                    "access": {"format": self._build_format("ACCESS")},
                },
                "filters": context_filters,
                "handlers": {
                    "console": {
                        "class": "logging.StreamHandler",
                        "formatter": "standard",
                        "level": "INFO",
                    },
                    "access_console": {
                        "class": "logging.StreamHandler",
                        "formatter": "access",
                        "level": "INFO",
                    },
                },
                "loggers": {
                    "uvicorn": {
                        "level": "INFO",
                        "handlers": ["console"],
                        "propagate": False,
                    },
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

        return self._base_config

    def _build_format(self, type: Literal["STANDARD", "ACCESS"]) -> str:
        """Build standard or access format string with all registered contexts."""
        if not self._context_registry:
            raise ValueError("LogConfigurator is not initialized yet")

        base = "[%(asctime)s][%(levelname)s]"
        if type == "ACCESS":
            base += "[ACCESS]"

        for name in self._context_registry.contexts.keys():
            base += f"[{name}: %({name})s]"

        if type == "ACCESS" and "response_time" in self._context_registry.contexts:
            base += "[response_time_ms: %(response_time_ms)s]"

        base += "[%(name)s]: %(message)s"
        return base

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
        custom = {}
        if self.config:
            custom = self.config.model_extra or {}

        merged = deep_merge_dicts(self.BASE_LOG_CONFIG, custom)

        if extra:
            merged = deep_merge_dicts(merged, extra)

        merged = self._auto_apply_filters(merged)

        if apply:
            logging.config.dictConfig(merged)
            logging.captureWarnings(True)

        return merged

    def _load_custom_config_file(self, log_path: str) -> dict:
        """Load a custom logging config located in `log_path`"""
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

        for _, handler_config in config["handlers"].items():
            auto_filters = handler_config.pop("auto_filters", True)
            if not auto_filters:
                continue

            excluded = set(handler_config.pop("exclude_filters", []))

            existing_filters = handler_config.get("filters", [])
            if not isinstance(existing_filters, list):
                existing_filters = []
                handler_config["filters"] = existing_filters

            existing_filter_set = set(existing_filters)

            filters_to_add = all_filter_names - excluded - existing_filter_set

            if filters_to_add or existing_filters:
                handler_config["filters"] = existing_filters + sorted(list(filters_to_add))

        return config
