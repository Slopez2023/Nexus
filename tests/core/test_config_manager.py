"""Tests for the Configuration Management System."""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from nexus.core.config_manager import (
    ConfigManager, AppConfig, DatabaseConfig, LoggingConfig,
    get_app_config, update_app_config, validate_current_config
)


class TestDatabaseConfig:
    """Test database configuration validation."""

    def test_valid_database_config(self):
        """Test valid database configuration."""
        config = DatabaseConfig(
            host="localhost",
            port=5432,
            database="test_db",
            user="test_user",
            password="test_pass",
            min_connections=1,
            max_connections=10
        )
        assert config.host == "localhost"
        assert config.port == 5432

    def test_invalid_port(self):
        """Test invalid port validation."""
        with pytest.raises(ValueError):
            DatabaseConfig(port=70000)  # Invalid port

    def test_invalid_connection_limits(self):
        """Test invalid connection limits."""
        with pytest.raises(ValueError):
            DatabaseConfig(min_connections=5, max_connections=3)  # min > max


class TestLoggingConfig:
    """Test logging configuration validation."""

    def test_valid_logging_config(self):
        """Test valid logging configuration."""
        config = LoggingConfig(
            level="INFO",
            directory="logs",
            json_format=False,
            max_file_size=10*1024*1024,
            backup_count=5
        )
        assert config.level == "INFO"

    def test_invalid_log_level(self):
        """Test invalid log level validation."""
        with pytest.raises(ValueError):
            LoggingConfig(level="INVALID")


class TestAppConfig:
    """Test application configuration validation."""

    def test_valid_app_config(self):
        """Test valid application configuration."""
        config = AppConfig(
            environment="development",
            debug=True,
            database=DatabaseConfig(database="test"),
            logging=LoggingConfig()
        )
        assert config.environment == "development"
        assert config.debug is True

    def test_production_validation_requires_password(self):
        """Test production environment requires database password."""
        with pytest.raises(ValueError, match="Database password required in production"):
            AppConfig(
                environment="production",
                database=DatabaseConfig(password=""),  # Empty password
                logging=LoggingConfig()
            )

    def test_production_validation_requires_api_keys(self):
        """Test production environment requires API keys."""
        with pytest.raises(ValueError, match="API keys required in production"):
            AppConfig(
                environment="production",
                database=DatabaseConfig(password="secret"),
                logging=LoggingConfig()
            )


class TestConfigManager:
    """Test configuration manager functionality."""

    @patch("nexus.core.config_manager.dotenv.load_dotenv")
    @patch("nexus.core.config_manager.ConfigManager._load_from_env")
    def test_config_manager_initialization(self, mock_load_env, mock_load_dotenv):
        """Test config manager initialization."""
        # Mock _load_from_env to return empty dict
        mock_load_env.return_value = {}

        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "test_config.json"

            # Create test config file
            test_config = {
                "environment": "testing",
                "debug": True,
                "database": {"database": "test_db"}
            }
            config_file.write_text(json.dumps(test_config))

            manager = ConfigManager(config_file)
            config = manager.get_config()

            assert config.environment == "testing"
            assert config.debug is True
            assert config.database.database == "test_db"

    def test_config_update_with_audit(self):
        """Test configuration updates with audit logging."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "test_config.json"

            with patch.dict("os.environ", {}, clear=True):
                manager = ConfigManager(config_file)

                # Update configuration (debug is True by default, set to False)
                updates = {"debug": False, "database": {"port": 5433}}
                success = manager.update_config(updates, "test_user")

                assert success is True

                # Check audit log
                audit_log = manager.get_audit_log()
                assert len(audit_log) == 1
                assert audit_log[0].user == "test_user"
                assert len(audit_log[0].changes) >= 1  # at least database.port

    @patch.dict("os.environ", {
        "APP_ENV": "staging",
        "DB_HOST": "staging-db.example.com",
        "LOG_LEVEL": "WARNING"
    })
    def test_environment_variable_override(self):
        """Test environment variable overrides."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "test_config.json"

            # Base config file
            base_config = {"environment": "development", "database": {"host": "localhost"}}
            config_file.write_text(json.dumps(base_config))

            manager = ConfigManager(config_file)
            config = manager.get_config()

            # Environment variables should override file
            assert config.environment == "staging"
            assert config.database.host == "staging-db.example.com"
            assert config.logging.level == "WARNING"

    def test_config_validation(self):
        """Test configuration validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "test_config.json"

            manager = ConfigManager(config_file)
            is_valid = manager.validate_config()

            assert is_valid is True

    def test_config_export(self):
        """Test configuration export."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "test_config.json"

            manager = ConfigManager(config_file)
            json_export = manager.export_config("json")

            # Should be valid JSON
            parsed = json.loads(json_export)
            assert "environment" in parsed
            assert "database" in parsed

    @patch("nexus.core.config_manager.dotenv.load_dotenv")
    @patch("nexus.core.config_manager.ConfigManager._load_from_env")
    def test_config_reload(self, mock_load_env, mock_load_dotenv):
        """Test configuration reload."""
        # Mock _load_from_env to return empty dict
        mock_load_env.return_value = {}

        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "test_config.json"

            manager = ConfigManager(config_file)

            # Initial config
            initial_env = manager.get_config().environment

            # Modify file
            new_config = {"environment": "modified"}
            config_file.write_text(json.dumps(new_config))

            # Reload
            reloaded = manager.reload_config()
            assert reloaded is True

            new_env = manager.get_config().environment
            assert new_env == "modified"


class TestGlobalConfigFunctions:
    """Test global configuration functions."""

    @patch("nexus.core.config_manager._config_manager", None)
    def test_get_app_config(self):
        """Test getting application config."""
        config = get_app_config()
        assert isinstance(config, AppConfig)
        assert config.environment in ["development", "testing"]

    @patch("nexus.core.config_manager._config_manager", None)
    def test_update_app_config(self):
        """Test updating application config."""
        updates = {"debug": True}
        success = update_app_config(updates, "test")
        assert success is True

    @patch("nexus.core.config_manager._config_manager", None)
    def test_validate_current_config(self):
        """Test validating current config."""
        is_valid = validate_current_config()
        assert is_valid is True
