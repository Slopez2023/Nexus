"""Configuration management utilities."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

from nexus.core.exceptions import ConfigurationError


class ConfigManager:
    """Manages configuration loading and validation."""

    def __init__(self, config_file: Optional[str] = None):
        """Initialize ConfigManager.

        Args:
            config_file: Path to configuration file. If None, uses defaults.
        """
        self.config_file = config_file or "config.json"
        self._config: Dict[str, Any] = {}

    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file.

        Returns:
            Configuration dictionary.

        Raises:
            ConfigurationError: If config file is invalid.
        """
        config_path = Path(self.config_file)
        if not config_path.exists():
            # Return default config
            self._config = self._get_default_config()
        else:
            try:
                import json
                with open(config_path, "r") as f:
                    self._config = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                raise ConfigurationError(f"Failed to load config: {e}") from e

        self._validate_config()
        return self._config

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value.

        Args:
            key: Configuration key.
            default: Default value if key not found.

        Returns:
            Configuration value.
        """
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set configuration value.

        Args:
            key: Configuration key.
            value: Value to set.
        """
        self._config[key] = value

    def save_config(self) -> None:
        """Save current configuration to file.

        Raises:
            ConfigurationError: If save fails.
        """
        try:
            import json
            config_path = Path(self.config_file)
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w") as f:
                json.dump(self._config, f, indent=2)
        except IOError as e:
            raise ConfigurationError(f"Failed to save config: {e}") from e

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration.

        Returns:
            Default config dictionary.
        """
        return {
            "database": {
                "host": "localhost",
                "port": 5432,
                "database": "nexus",
                "user": "nexus_user",
            },
            "logging": {
                "level": "INFO",
                "file": "nexus.log",
            },
            "risk": {
                "max_position_size": 0.1,  # 10% of capital
                "max_drawdown": 0.2,  # 20% max drawdown
            },
        }

    def _validate_config(self) -> None:
        """Validate configuration.

        Raises:
            ConfigurationError: If config is invalid.
        """
        # Basic validation - can be extended
        if "database" in self._config:
            db_config = self._config["database"]
            if not isinstance(db_config.get("port"), int):
                raise ConfigurationError("Database port must be an integer")
