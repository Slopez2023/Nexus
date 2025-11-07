"""Tests for ConfigManager in nexus.core.config."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nexus.core.config import ConfigManager
from nexus.core.exceptions import ConfigurationError


class TestConfigManager(unittest.TestCase):
    """Test the ConfigManager class."""

    def test_init_default_config_file(self):
        """Test ConfigManager initialization with default config file."""
        manager = ConfigManager()
        self.assertEqual(manager.config_file, "config.json")
        self.assertEqual(manager._config, {})

    def test_init_custom_config_file(self):
        """Test ConfigManager initialization with custom config file."""
        manager = ConfigManager("custom.json")
        self.assertEqual(manager.config_file, "custom.json")

    def test_load_config_defaults_when_no_file(self):
        """Test loading default config when file doesn't exist."""
        manager = ConfigManager("nonexistent.json")
        config = manager.load_config()

        self.assertIn("database", config)
        self.assertIn("logging", config)
        self.assertIn("risk", config)
        self.assertEqual(config["database"]["port"], 5432)

    def test_load_config_from_file(self):
        """Test loading config from JSON file."""
        config_data = {"test_key": "test_value", "number": 42}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name

        try:
            manager = ConfigManager(config_file)
            config = manager.load_config()

            self.assertEqual(config["test_key"], "test_value")
            self.assertEqual(config["number"], 42)
        finally:
            Path(config_file).unlink()

    def test_load_config_invalid_json(self):
        """Test loading config with invalid JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("invalid json content")
            config_file = f.name

        try:
            manager = ConfigManager(config_file)
            with self.assertRaises(ConfigurationError):
                manager.load_config()
        finally:
            Path(config_file).unlink()

    def test_get_config_value(self):
        """Test getting configuration values."""
        manager = ConfigManager()
        manager.set("test_key", "test_value")

        self.assertEqual(manager.get("test_key"), "test_value")
        self.assertIsNone(manager.get("missing_key"))
        self.assertEqual(manager.get("missing_key", "default"), "default")

    def test_set_config_value(self):
        """Test setting configuration values."""
        manager = ConfigManager()
        manager.set("test_key", "test_value")

        self.assertEqual(manager._config["test_key"], "test_value")

    def test_save_config(self):
        """Test saving configuration to file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "test_config.json"
            manager = ConfigManager(str(config_file))

            manager.set("test_key", "test_value")
            manager.save_config()

            self.assertTrue(config_file.exists())
            with open(config_file, "r") as f:
                saved_config = json.load(f)
                self.assertEqual(saved_config["test_key"], "test_value")

    def test_save_config_creates_directory(self):
        """Test that save_config creates parent directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "subdir" / "config.json"
            manager = ConfigManager(str(config_file))

            manager.set("key", "value")
            manager.save_config()

            self.assertTrue(config_file.exists())
            self.assertTrue(config_file.parent.exists())

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

        with self.assertRaises(ConfigurationError):
            manager._validate_config()
