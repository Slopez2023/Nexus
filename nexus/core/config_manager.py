"""Configuration Management System for NEXUS.

Provides type-safe, hierarchical configuration management with validation,
audit logging, and environment support.
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, Union
from datetime import datetime
from dataclasses import dataclass

from pydantic import BaseModel, Field, field_validator, model_validator
import dotenv

from nexus.core.logging_config import get_nexus_logger


class DatabaseConfig(BaseModel):
    """Database configuration with validation."""

    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, ge=1, le=65535, description="Database port")
    database: str = Field(default="nexus_trading", description="Database name")
    user: str = Field(default="nexus_user", description="Database user")
    password: str = Field(default="", description="Database password")
    min_connections: int = Field(default=1, ge=1, description="Minimum connection pool size")
    max_connections: int = Field(default=10, ge=1, description="Maximum connection pool size")

    @field_validator('max_connections')
    @classmethod
    def validate_connection_limits(cls, v, info):
        """Ensure max connections >= min connections."""
        if info.data and 'min_connections' in info.data and v < info.data['min_connections']:
            raise ValueError('max_connections must be >= min_connections')
        return v


class APIConfig(BaseModel):
    """External API configuration."""

    massive_key: Optional[str] = Field(default=None, description="Polygon.io API key")
    openrouter_key: Optional[str] = Field(default=None, description="OpenRouter API key")
    deepseek_key: Optional[str] = Field(default=None, description="DeepSeek API key")
    coingecko_key: Optional[str] = Field(default=None, description="CoinGecko API key")


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = Field(default="INFO", description="Log level")
    directory: str = Field(default="logs", description="Log directory")
    json_format: bool = Field(default=False, description="Use JSON format for logs")
    max_file_size: int = Field(default=10*1024*1024, ge=1024, description="Max log file size in bytes")
    backup_count: int = Field(default=5, ge=0, description="Number of backup log files")

    @field_validator('level')
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'Invalid log level. Must be one of: {valid_levels}')
        return v.upper()


class BackupConfig(BaseModel):
    """Backup configuration."""

    directory: str = Field(default="backups", description="Backup directory")
    retention_days: int = Field(default=30, ge=1, description="Days to retain backups")
    schedule: str = Field(default="daily", description="Backup schedule")


class MonitoringConfig(BaseModel):
    """Monitoring configuration."""

    enabled: bool = Field(default=True, description="Enable monitoring")
    interval_seconds: int = Field(default=300, ge=30, description="Monitoring interval")
    alert_email: Optional[str] = Field(default=None, description="Email for alerts")


class AppConfig(BaseModel):
    """Main application configuration."""

    environment: str = Field(default="development", description="Application environment")
    debug: bool = Field(default=False, description="Debug mode")
    version: str = Field(default="1.0.0", description="Application version")

    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    backup: BackupConfig = Field(default_factory=BackupConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)

    @model_validator(mode='after')
    def validate_environment_config(self):
        """Validate configuration based on environment."""
        if self.environment == 'production':
            # Stricter validation for production
            if not self.database.password:
                raise ValueError('Database password required in production')
            if not self.api.massive_key:
                raise ValueError('API keys required in production')

        return self


@dataclass
class ConfigChange:
    """Represents a configuration change for auditing."""

    timestamp: datetime
    user: str
    changes: Dict[str, Dict[str, Any]]
    checksum: str


class ConfigManager:
    """Centralized configuration management with validation and auditing."""

    def __init__(self, config_file: Optional[Union[str, Path]] = None):
        self.logger = get_nexus_logger("config.manager")
        self.config_file = Path(config_file or "config.json")
        self._config: Optional[AppConfig] = None
        self._audit_log: list[ConfigChange] = []

        # Load environment variables
        dotenv.load_dotenv()

        # Load initial configuration
        self._load_config()

    def _load_config(self) -> AppConfig:
        """Load configuration with hierarchy: defaults → file → env → overrides."""
        self.logger.debug("Loading configuration")

        # Start with defaults
        config_dict = {}

        # Load from file if exists
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    file_config = json.load(f)
                    config_dict.update(file_config)
                    self.logger.debug(f"Loaded config from {self.config_file}")
            except Exception as e:
                self.logger.warning(f"Failed to load config file {self.config_file}: {e}")

        # Override with environment variables
        env_config = self._load_from_env()
        config_dict = self._merge_configs(config_dict, env_config)

        # Validate and create config
        try:
            self._config = AppConfig(**config_dict)
            self.logger.info(f"Configuration loaded successfully for environment: {self._config.environment}")
            return self._config
        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            raise

    def _load_from_env(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        return {
            "environment": os.getenv("APP_ENV", "development"),
            "debug": os.getenv("DEBUG", "false").lower() == "true",
            "version": os.getenv("APP_VERSION", "1.0.0"),
            "database": {
                "host": os.getenv("DB_HOST", "localhost"),
                "port": int(os.getenv("DB_PORT", "5432")),
                "database": os.getenv("DB_NAME", "nexus_trading"),
                "user": os.getenv("DB_USER", "nexus_user"),
                "password": os.getenv("DB_PASSWORD", ""),
                "min_connections": int(os.getenv("DB_MIN_CONNECTIONS", "1")),
                "max_connections": int(os.getenv("DB_MAX_CONNECTIONS", "10")),
            },
            "api": {
                "massive_key": os.getenv("MASSIVE_API_KEY"),
                "openrouter_key": os.getenv("OPENROUTER_API_KEY"),
                "deepseek_key": os.getenv("DEEPSEEK_API_KEY"),
                "coingecko_key": os.getenv("COINGECKO_API_KEY"),
            },
            "logging": {
                "level": os.getenv("LOG_LEVEL", "INFO"),
                "directory": os.getenv("LOG_DIR", "logs"),
                "json_format": os.getenv("LOG_JSON", "false").lower() == "true",
                "max_file_size": int(os.getenv("LOG_MAX_SIZE", str(10*1024*1024))),
                "backup_count": int(os.getenv("LOG_BACKUP_COUNT", "5")),
            },
            "backup": {
                "directory": os.getenv("BACKUP_DIR", "backups"),
                "retention_days": int(os.getenv("BACKUP_RETENTION_DAYS", "30")),
                "schedule": os.getenv("BACKUP_SCHEDULE", "daily"),
            },
            "monitoring": {
                "enabled": os.getenv("MONITORING_ENABLED", "true").lower() == "true",
                "interval_seconds": int(os.getenv("MONITORING_INTERVAL", "300")),
                "alert_email": os.getenv("ALERT_EMAIL"),
            }
        }

    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge configuration dictionaries."""
        result = base.copy()

        for key, value in override.items():
            if isinstance(value, dict) and key in result and isinstance(result[key], dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value

        return result

    def get_config(self) -> AppConfig:
        """Get the current validated configuration."""
        if self._config is None:
            self._load_config()
        return self._config

    def update_config(self, updates: Dict[str, Any], user: str = "system") -> bool:
        """Update configuration with validation and auditing."""
        try:
            # Get current config
            current = self.get_config()

            # Create updated config dict
            current_dict = current.model_dump()
            updated_dict = self._merge_configs(current_dict, updates)

            # Validate new configuration
            new_config = AppConfig(**updated_dict)

            # Calculate changes for audit
            changes = self._calculate_changes(current_dict, updated_dict)

            if changes:
                # Create audit entry
                checksum = self._calculate_checksum(updated_dict)
                audit_entry = ConfigChange(
                    timestamp=datetime.now(),
                    user=user,
                    changes=changes,
                    checksum=checksum
                )
                self._audit_log.append(audit_entry)

                # Save to file
                self.config_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.config_file, 'w') as f:
                    json.dump(updated_dict, f, indent=2, default=str)

                # Update in-memory config
                self._config = new_config

                self.logger.info(f"Configuration updated by {user}: {len(changes)} changes")
                return True
            else:
                self.logger.info("No configuration changes detected")
                return True

        except Exception as e:
            self.logger.error(f"Configuration update failed: {e}")
            return False

    def _calculate_changes(self, old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Calculate what changed between configs."""
        changes = {}

        def deep_diff(path: str, old_val: Any, new_val: Any):
            if old_val != new_val:
                if isinstance(old_val, dict) and isinstance(new_val, dict):
                    for key in set(old_val.keys()) | set(new_val.keys()):
                        deep_diff(f"{path}.{key}", old_val.get(key), new_val.get(key))
                else:
                    changes[path] = {"old": old_val, "new": new_val}

        deep_diff("root", old, new)
        return changes

    def _calculate_checksum(self, config: Dict[str, Any]) -> str:
        """Calculate configuration checksum for integrity."""
        config_str = json.dumps(config, sort_keys=True, default=str)
        return hashlib.sha256(config_str.encode()).hexdigest()

    def validate_config(self) -> bool:
        """Validate current configuration."""
        try:
            config = self.get_config()
            # Additional validation logic can go here
            return True
        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            return False

    def get_audit_log(self, limit: int = 50) -> list[ConfigChange]:
        """Get configuration audit log."""
        return self._audit_log[-limit:] if limit > 0 else self._audit_log

    def export_config(self, format: str = "json") -> str:
        """Export configuration in specified format."""
        config = self.get_config()

        if format.lower() == "json":
            return config.model_dump_json(indent=2)
        elif format.lower() == "yaml":
            try:
                import yaml
                return yaml.dump(config.model_dump(), default_flow_style=False)
            except ImportError:
                raise ValueError("YAML support requires PyYAML package")
        else:
            raise ValueError(f"Unsupported export format: {format}")

    def reload_config(self) -> bool:
        """Reload configuration from sources."""
        try:
            old_config = self._config
            self._config = None  # Force reload
            new_config = self.get_config()

            if old_config != new_config:
                self.logger.info("Configuration reloaded with changes")
                return True
            else:
                self.logger.info("Configuration reloaded (no changes)")
                return True
        except Exception as e:
            self.logger.error(f"Configuration reload failed: {e}")
            return False


# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None

def get_config_manager(config_file: Optional[Union[str, Path]] = None) -> ConfigManager:
    """Get or create the global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_file)
    return _config_manager

def get_app_config() -> AppConfig:
    """Get the current application configuration."""
    return get_config_manager().get_config()

# Convenience functions
def init_config(config_file: Optional[Union[str, Path]] = None) -> ConfigManager:
    """Initialize configuration system."""
    return get_config_manager(config_file)

def update_app_config(updates: Dict[str, Any], user: str = "system") -> bool:
    """Update application configuration."""
    return get_config_manager().update_config(updates, user)

def validate_current_config() -> bool:
    """Validate current configuration."""
    return get_config_manager().validate_config()
