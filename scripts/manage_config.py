#!/usr/bin/env python3
"""Configuration Management CLI for NEXUS.

Manage application configuration with validation, auditing, and environment support.
"""

import sys
import json
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from nexus.core.config_manager import (
    get_config_manager, get_app_config, update_app_config,
    validate_current_config, ConfigManager
)
from nexus.core.logging_config import get_nexus_logger


def main():
    """CLI interface for configuration management."""
    parser = argparse.ArgumentParser(description="NEXUS Configuration Manager")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Show current configuration
    subparsers.add_parser("show", help="Show current configuration")

    # Validate configuration
    subparsers.add_parser("validate", help="Validate current configuration")

    # Update configuration
    update_parser = subparsers.add_parser("update", help="Update configuration")
    update_parser.add_argument("key", help="Configuration key (dot notation)")
    update_parser.add_argument("value", help="New value (JSON)")
    update_parser.add_argument("--user", default="cli", help="User making change")

    # Export configuration
    export_parser = subparsers.add_parser("export", help="Export configuration")
    export_parser.add_argument("--format", choices=["json", "yaml"],
                              default="json", help="Export format")
    export_parser.add_argument("--file", help="Output file")

    # Audit log
    audit_parser = subparsers.add_parser("audit", help="Show configuration audit log")
    audit_parser.add_argument("--limit", type=int, default=10,
                             help="Number of entries to show")

    # Generate environment-specific config
    gen_parser = subparsers.add_parser("generate", help="Generate config template")
    gen_parser.add_argument("environment", choices=["development", "staging", "production"],
                           help="Target environment")
    gen_parser.add_argument("--output", help="Output file")

    args = parser.parse_args()

    logger = get_nexus_logger("config.cli")

    if args.command == "show":
        config = get_app_config()
        print("=== Current NEXUS Configuration ===")
        print(f"Environment: {config.environment}")
        print(f"Version: {config.version}")
        print(f"Debug: {config.debug}")
        print()

        print("Database:")
        print(f"  Host: {config.database.host}")
        print(f"  Port: {config.database.port}")
        print(f"  Database: {config.database.database}")
        print(f"  User: {config.database.user}")
        print(f"  Connections: {config.database.min_connections}-{config.database.max_connections}")
        print()

        print("API Keys:")
        print(f"  Polygon: {'✓ Set' if config.api.massive_key else '✗ Not set'}")
        print(f"  OpenRouter: {'✓ Set' if config.api.openrouter_key else '✗ Not set'}")
        print(f"  DeepSeek: {'✓ Set' if config.api.deepseek_key else '✗ Not set'}")
        print(f"  CoinGecko: {'✓ Set' if config.api.coingecko_key else '✗ Not set'}")
        print()

        print("Logging:")
        print(f"  Level: {config.logging.level}")
        print(f"  Directory: {config.logging.directory}")
        print(f"  JSON Format: {config.logging.json_format}")
        print(f"  Max File Size: {config.logging.max_file_size // (1024*1024)}MB")
        print(f"  Backup Count: {config.logging.backup_count}")
        print()

        print("Backup:")
        print(f"  Directory: {config.backup.directory}")
        print(f"  Retention: {config.backup.retention_days} days")
        print(f"  Schedule: {config.backup.schedule}")
        print()

        print("Monitoring:")
        print(f"  Enabled: {config.monitoring.enabled}")
        print(f"  Interval: {config.monitoring.interval_seconds} seconds")
        print(f"  Alert Email: {config.monitoring.alert_email or 'Not set'}")

    elif args.command == "validate":
        is_valid = validate_current_config()
        if is_valid:
            print("✅ Configuration is valid")
            config = get_app_config()
            print(f"Environment: {config.environment}")
        else:
            print("❌ Configuration validation failed")
            sys.exit(1)

    elif args.command == "update":
        # Parse the key path and value
        key_path = args.key.split('.')
        try:
            value = json.loads(args.value)
        except json.JSONDecodeError:
            # Try as string
            value = args.value

        # Build update dictionary
        update_dict = value
        for key in reversed(key_path):
            update_dict = {key: update_dict}

        success = update_app_config(update_dict, args.user)
        if success:
            print(f"✅ Configuration updated: {args.key} = {value}")
        else:
            print("❌ Configuration update failed")
            sys.exit(1)

    elif args.command == "export":
        from nexus.core.config_manager import ConfigManager
        manager = get_config_manager()

        try:
            config_str = manager.export_config(args.format)
            if args.file:
                Path(args.file).write_text(config_str)
                print(f"✅ Configuration exported to {args.file}")
            else:
                print(config_str)
        except Exception as e:
            print(f"❌ Export failed: {e}")
            sys.exit(1)

    elif args.command == "audit":
        manager = get_config_manager()
        audit_log = manager.get_audit_log(args.limit)

        if not audit_log:
            print("No audit entries found")
            return

        print(f"=== Configuration Audit Log (Last {len(audit_log)} entries) ===")
        for entry in audit_log:
            print(f"\n{entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {entry.user}")
            print(f"Changes: {len(entry.changes)}")
            for path, change in entry.changes.items():
                print(f"  {path}: {change['old']} → {change['new']}")
            print(f"Checksum: {entry.checksum[:8]}...")

    elif args.command == "generate":
        # Generate environment-specific configuration
        base_config = {
            "environment": args.environment,
            "debug": args.environment == "development",
            "version": "1.0.0",
            "database": {
                "host": "localhost" if args.environment == "development" else "nexus-postgres",
                "port": 5432,
                "database": "nexus_trading",
                "user": "nexus_user",
                "password": "CHANGE_THIS_IN_PRODUCTION",
                "min_connections": 1,
                "max_connections": 5 if args.environment == "development" else 20
            },
            "api": {
                "massive_key": "YOUR_POLYGON_API_KEY",
                "openrouter_key": "YOUR_OPENROUTER_KEY" if args.environment != "development" else None,
                "deepseek_key": "YOUR_DEEPSEEK_KEY" if args.environment != "development" else None,
                "coingecko_key": "YOUR_COINGECKO_KEY" if args.environment != "development" else None
            },
            "logging": {
                "level": "DEBUG" if args.environment == "development" else "INFO",
                "directory": "logs",
                "json_format": args.environment == "production",
                "max_file_size": 10*1024*1024,
                "backup_count": 5
            },
            "backup": {
                "directory": "backups",
                "retention_days": 7 if args.environment == "development" else 30,
                "schedule": "daily"
            },
            "monitoring": {
                "enabled": True,
                "interval_seconds": 60 if args.environment == "development" else 300,
                "alert_email": "alerts@nexus-trading.com" if args.environment == "production" else None
            }
        }

        config_json = json.dumps(base_config, indent=2)

        if args.output:
            Path(args.output).write_text(config_json)
            print(f"✅ Generated {args.environment} configuration: {args.output}")
        else:
            print(f"=== Generated {args.environment} Configuration ===")
            print(config_json)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
