"""Tests for ConfigManager in nexus.core.config."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from nexus.core.config import ConfigManager
from nexus.core.exceptions import ConfigurationError


class TestConfigManager:
    """Test the ConfigManager class."""

    def test_init_default_config_file(self):
        """Test ConfigManager initialization with default config file."""
        manager = ConfigManager()
        assert manager.config_file == "config.json"
        assert manager._config == {}

    def test_init_custom_config_file(self):
        """Test ConfigManager initialization with custom config file."""
        manager = ConfigManager("custom.json")
        assert manager.config_file == "custom.json"

    def test_load_config_defaults_when_no_file(self):
        """Test loading default config when file doesn't exist."""
        manager = ConfigManager("nonexistent.json")
        config = manager.load_config()

        assert "database" in config
        assert "logging" in config
        assert "risk" in config
        assert config["database"]["port"] == 5432

    def test_load_config_from_file(self):
        """Test loading config from JSON file."""
        config_data = {"test_key": "test_value", "number": 42}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name

        try:
            manager = ConfigManager(config_file)
            config = manager.load_config()

            assert config["test_key"] == "test_value"
            assert config["number"] == 42
        finally:
            Path(config_file).unlink()

    def test_load_config_invalid_json(self):
        """Test loading config with invalid JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("invalid json content")
            config_file = f.name

        try:
            manager = ConfigManager(config_file)
            with pytest.raises(ConfigurationError):
                manager.load_config()
        finally:
            Path(config_file).unlink()

    def test_get_config_value(self):
        """Test getting configuration values."""
        manager = ConfigManager()
        manager.set("test_key", "test_value")

        assert manager.get("test_key") == "test_value"
        assert manager.get("missing_key") is None
        assert manager.get("missing_key", "default") == "default"

    def test_set_config_value(self):
        """Test setting configuration values."""
        manager = ConfigManager()
        manager.set("test_key", "test_value")

        assert manager._config["test_key"] == "test_value"

    def test_save_config(self):
        """Test saving configuration to file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "test_config.json"
            manager = ConfigManager(str(config_file))

            manager.set("test_key", "test_value")
            manager.save_config()

            assert config_file.exists()
            with open(config_file, "r") as f:
                saved_config = json.load(f)
                assert saved_config["test_key"] == "test_value"

    def test_save_config_creates_directory(self):
        """Test that save_config creates parent directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "subdir" / "config.json"
            manager = ConfigManager(str(config_file))

            manager.set("key", "value")
            manager.save_config()

            assert config_file.exists()
            assert config_file.parent.exists()

    def test_validate_config_valid(self):
        """Test config validation with valid config."""
        manager = ConfigManager()
        manager._config = {"database": {"port": 5432}}
        # Should not raise
        manager._validate_config()

    def test_validate_config_invalid_port(self):
        """Test config validation with invalid port type."""
        manager = ConfigManager()
        manager._config = {"database": {"port": "invalid"}}

        with pytest.raises(ConfigurationError):
            manager._validate_config()
