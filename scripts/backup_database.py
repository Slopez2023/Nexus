#!/usr/bin/env python3
"""Database backup and restore utilities for NEXUS.

Provides automated backup creation, integrity verification,
and restore procedures for PostgreSQL database.
"""

import os
import sys
import gzip
import shutil
import hashlib
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from nexus.core.logging_config import get_nexus_logger
from nexus.core.database import DatabaseConfig


class DatabaseBackupManager:
    """PostgreSQL backup and restore manager."""

    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or DatabaseConfig.from_env()
        self.logger = get_nexus_logger("backup.database")

        # Backup configuration
        self.backup_dir = Path(os.getenv("BACKUP_DIR", "backups"))
        self.backup_dir.mkdir(exist_ok=True)

        self.retention_days = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))

    def create_backup(self, backup_type: str = "full") -> Optional[Path]:
        """Create database backup."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"nexus_trading_{backup_type}_{timestamp}"

        if backup_type == "full":
            return self._create_pg_dump_backup(backup_name)
        elif backup_type == "schema":
            return self._create_schema_backup(backup_name)
        else:
            self.logger.error(f"Unknown backup type: {backup_type}")
            return None

    def _create_pg_dump_backup(self, backup_name: str) -> Optional[Path]:
        """Create full PostgreSQL dump backup."""
        try:
            backup_file = self.backup_dir / f"{backup_name}.sql.gz"

            # pg_dump command
            cmd = [
                "pg_dump",
                f"--host={self.config.host}",
                f"--port={self.config.port}",
                f"--username={self.config.user}",
                f"--dbname={self.config.database}",
                "--no-password",
                "--format=custom",  # Custom format for better compression
                "--compress=9",     # Maximum compression
                "--verbose"
            ]

            # Set password environment
            env = os.environ.copy()
            env["PGPASSWORD"] = self.config.password

            self.logger.info(f"Creating database backup: {backup_file}")

            with gzip.open(backup_file, 'wb') as f:
                result = subprocess.run(
                    cmd,
                    env=env,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    text=True
                )

            if result.returncode == 0:
                # Calculate checksum
                checksum = self._calculate_checksum(backup_file)
                checksum_file = backup_file.with_suffix('.checksum')
                checksum_file.write_text(f"{backup_file.name}\n{checksum}")

                self.logger.info(f"Backup completed: {backup_file} ({backup_file.stat().st_size} bytes)")
                return backup_file
            else:
                self.logger.error(f"Backup failed: {result.stderr}")
                if backup_file.exists():
                    backup_file.unlink()
                return None

        except Exception as e:
            self.logger.error(f"Backup creation failed: {e}")
            return None

    def _create_schema_backup(self, backup_name: str) -> Optional[Path]:
        """Create schema-only backup."""
        try:
            backup_file = self.backup_dir / f"{backup_name}_schema.sql"

            cmd = [
                "pg_dump",
                f"--host={self.config.host}",
                f"--port={self.config.port}",
                f"--username={self.config.user}",
                f"--dbname={self.config.database}",
                "--no-password",
                "--schema-only",    # Schema only
                "--no-owner",       # Don't set ownership
                "--no-privileges"   # Don't dump privileges
            ]

            env = os.environ.copy()
            env["PGPASSWORD"] = self.config.password

            self.logger.info(f"Creating schema backup: {backup_file}")

            with open(backup_file, 'w') as f:
                result = subprocess.run(
                    cmd,
                    env=env,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    text=True
                )

            if result.returncode == 0:
                self.logger.info(f"Schema backup completed: {backup_file}")
                return backup_file
            else:
                self.logger.error(f"Schema backup failed: {result.stderr}")
                if backup_file.exists():
                    backup_file.unlink()
                return None

        except Exception as e:
            self.logger.error(f"Schema backup creation failed: {e}")
            return None

    def restore_backup(self, backup_file: Path, target_db: Optional[str] = None) -> bool:
        """Restore database from backup."""
        try:
            if not backup_file.exists():
                self.logger.error(f"Backup file does not exist: {backup_file}")
                return False

            # Verify checksum if available
            if not self._verify_checksum(backup_file):
                self.logger.error("Backup file checksum verification failed")
                return False

            target_database = target_db or self.config.database

            # pg_restore command for custom format
            if backup_file.suffix == '.gz':
                # Decompress and restore
                cmd = [
                    "pg_restore",
                    f"--host={self.config.host}",
                    f"--port={self.config.port}",
                    f"--username={self.config.user}",
                    f"--dbname={target_database}",
                    "--no-password",
                    "--clean",        # Clean (drop) database objects before recreating
                    "--create",       # Create the database
                    "--verbose"
                ]

                env = os.environ.copy()
                env["PGPASSWORD"] = self.config.password

                self.logger.info(f"Restoring database from: {backup_file}")

                with gzip.open(backup_file, 'rb') as f:
                    result = subprocess.run(
                        cmd,
                        env=env,
                        stdin=f,
                        stderr=subprocess.PIPE,
                        text=True
                    )
            else:
                # SQL format
                cmd = [
                    "psql",
                    f"--host={self.config.host}",
                    f"--port={self.config.port}",
                    f"--username={self.config.user}",
                    f"--dbname={target_database}",
                    "--no-password"
                ]

                env = os.environ.copy()
                env["PGPASSWORD"] = self.config.password

                self.logger.info(f"Restoring database from SQL: {backup_file}")

                with open(backup_file, 'r') as f:
                    result = subprocess.run(
                        cmd,
                        env=env,
                        stdin=f,
                        stderr=subprocess.PIPE,
                        text=True
                    )

            if result.returncode == 0:
                self.logger.info(f"Database restore completed successfully")
                return True
            else:
                self.logger.error(f"Database restore failed: {result.stderr}")
                return False

        except Exception as e:
            self.logger.error(f"Database restore failed: {e}")
            return False

    def list_backups(self) -> List[Dict[str, Any]]:
        """List available backups."""
        backups = []

        for backup_file in self.backup_dir.glob("nexus_trading_*.sql*"):
            if backup_file.suffix in ['.gz', '.sql']:
                stat = backup_file.stat()
                backups.append({
                    "filename": backup_file.name,
                    "path": backup_file,
                    "size": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_ctime),
                    "type": "schema" if "schema" in backup_file.name else "full"
                })

        return sorted(backups, key=lambda x: x["created"], reverse=True)

    def cleanup_old_backups(self) -> int:
        """Remove backups older than retention period."""
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        removed_count = 0

        for backup_file in self.backup_dir.glob("nexus_trading_*.sql*"):
            if datetime.fromtimestamp(backup_file.stat().st_ctime) < cutoff_date:
                # Remove backup file and checksum
                backup_file.unlink()
                checksum_file = backup_file.with_suffix('.checksum')
                if checksum_file.exists():
                    checksum_file.unlink()

                self.logger.info(f"Removed old backup: {backup_file.name}")
                removed_count += 1

        if removed_count > 0:
            self.logger.info(f"Cleaned up {removed_count} old backups")
        else:
            self.logger.info("No old backups to clean up")

        return removed_count

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of file."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _verify_checksum(self, backup_file: Path) -> bool:
        """Verify backup file checksum."""
        checksum_file = backup_file.with_suffix('.checksum')

        if not checksum_file.exists():
            self.logger.warning(f"No checksum file found for {backup_file}")
            return True  # Allow restore without checksum

        try:
            with open(checksum_file, 'r') as f:
                lines = f.readlines()
                if len(lines) >= 2:
                    expected_checksum = lines[1].strip()
                    actual_checksum = self._calculate_checksum(backup_file)
                    return expected_checksum == actual_checksum
        except Exception as e:
            self.logger.error(f"Checksum verification failed: {e}")

        return False

    def get_backup_stats(self) -> Dict[str, Any]:
        """Get backup statistics."""
        backups = self.list_backups()

        total_size = sum(b["size"] for b in backups)
        full_backups = [b for b in backups if b["type"] == "full"]
        schema_backups = [b for b in backups if b["type"] == "schema"]

        return {
            "total_backups": len(backups),
            "full_backups": len(full_backups),
            "schema_backups": len(schema_backups),
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "oldest_backup": min((b["created"] for b in backups), default=None),
            "newest_backup": max((b["created"] for b in backups), default=None),
            "retention_days": self.retention_days
        }


def main():
    """CLI interface for backup operations."""
    import argparse

    parser = argparse.ArgumentParser(description="NEXUS Database Backup Manager")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Create backup
    create_parser = subparsers.add_parser("create", help="Create database backup")
    create_parser.add_argument("--type", choices=["full", "schema"],
                              default="full", help="Backup type")

    # Restore backup
    restore_parser = subparsers.add_parser("restore", help="Restore database from backup")
    restore_parser.add_argument("backup_file", help="Backup file to restore")
    restore_parser.add_argument("--target-db", help="Target database name")

    # List backups
    subparsers.add_parser("list", help="List available backups")

    # Cleanup old backups
    subparsers.add_parser("cleanup", help="Remove old backups")

    # Stats
    subparsers.add_parser("stats", help="Show backup statistics")

    args = parser.parse_args()

    manager = DatabaseBackupManager()

    if args.command == "create":
        backup_file = manager.create_backup(args.type)
        if backup_file:
            print(f"✅ Backup created: {backup_file}")
        else:
            print("❌ Backup failed")
            sys.exit(1)

    elif args.command == "restore":
        backup_path = Path(args.backup_file)
        success = manager.restore_backup(backup_path, args.target_db)
        if success:
            print(f"✅ Database restored from: {backup_path}")
        else:
            print("❌ Restore failed")
            sys.exit(1)

    elif args.command == "list":
        backups = manager.list_backups()
        if not backups:
            print("No backups found")
            return

        print(f"{'Filename':<50} {'Type':<8} {'Size':<10} {'Created'}")
        print("-" * 80)
        for backup in backups:
            size_mb = backup["size"] / (1024 * 1024)
            print(f"{backup['filename']:<50} {backup['type']:<8} {size_mb:<10.1f}MB {backup['created'].strftime('%Y-%m-%d %H:%M')}")

    elif args.command == "cleanup":
        removed = manager.cleanup_old_backups()
        print(f"✅ Cleaned up {removed} old backups")

    elif args.command == "stats":
        stats = manager.get_backup_stats()
        print(f"📊 Database Backup Statistics")
        print(f"Total backups: {stats['total_backups']}")
        print(f"Full backups: {stats['full_backups']}")
        print(f"Schema backups: {stats['schema_backups']}")
        print(f"Total size: {stats['total_size_mb']:.1f} MB")
        if stats['oldest_backup']:
            print(f"Date range: {stats['oldest_backup'].strftime('%Y-%m-%d')} to {stats['newest_backup'].strftime('%Y-%m-%d')}")
        print(f"Retention: {stats['retention_days']} days")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
