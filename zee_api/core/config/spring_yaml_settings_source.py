import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, YamlConfigSettingsSource


class SpringYamlSettingsSource(YamlConfigSettingsSource):
    """Custom settings source that reads YAML and substitutes environment variables."""

    def __init__(self, settings_cls: type[BaseSettings]):
        yaml_file_path = settings_cls.model_config.get("yaml_file", "")

        self.yaml_file = Path(str(yaml_file_path))
        self._settings_data = self._load_yaml()

    def _load_yaml(self) -> dict[str, Any]:
        """Load YAML file and return parsed data."""
        if not self.yaml_file.exists():
            return {}

        with open(self.yaml_file, "r") as f:
            return yaml.safe_load(f) or {}

    def _substitute_env_vars(self, value: Any) -> Any:
        """
        Recursively substitute environment variables in values.
        Supports syntax: ${ENV_VAR:default_value} or ${ENV_VAR}
        """
        if isinstance(value, str):
            pattern = r"\$\{([^}:]+)(?::([^}]*))?\}"

            def replace_env(match: re.Match):
                env_var = match.group(1)
                default_val = match.group(2) if match.group(2) is not None else ""

                return os.environ.get(env_var, default_val)

            return re.sub(pattern, replace_env, value)

        elif isinstance(value, dict):
            return {k: self._substitute_env_vars(v) for k, v in value.items()}

        elif isinstance(value, list):
            return [self._substitute_env_vars(item) for item in value]

        return value

    def __call__(self) -> dict[str, Any]:
        """Return settings with environment variable substitution."""
        return self._substitute_env_vars(self._settings_data)

    def get_field_value(self, field, field_name: str) -> tuple[Any, str, bool]:
        return None, "", False
