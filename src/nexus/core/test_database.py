"""Test database utilities for NEXUS.

Provides isolated testing environment with automatic setup/teardown,
test data generation, and database state management.
"""

import os
import uuid
import tempfile
from contextlib import contextmanager
from typing import Dict, Any, Optional, Generator
from pathlib import Path

from nexus.core.database import DatabaseManager, DatabaseConfig
from nexus.core.logging_config import get_nexus_logger


class TestDatabaseManager:
    """Isolated test database manager."""

    def __init__(self, base_config: Optional[DatabaseConfig] = None):
        self.base_config = base_config or DatabaseConfig.from_env()
        self.logger = get_nexus_logger("test.database")
        self.test_databases: Dict[str, str] = {}

    @contextmanager
    def create_test_database(self, schema_file: Optional[Path] = None) -> Generator[DatabaseManager, None, None]:
        """Create isolated test database with automatic cleanup."""
        test_db_name = f"nexus_test_{uuid.uuid4().hex[:8]}"

        try:
            # Create test database
            self._create_database(test_db_name)

            # Set up test configuration
            test_config = DatabaseConfig(
                host=self.base_config.host,
                port=self.base_config.port,
                database=test_db_name,
                user=self.base_config.user,
                password=self.base_config.password
            )

            # Initialize test database manager
            test_db = DatabaseManager(test_config)

            # Load schema if provided
            if schema_file and schema_file.exists():
                self._load_schema(test_db, schema_file)

            # Seed with test data
            self._seed_test_data(test_db)

            self.logger.info(f"Created test database: {test_db_name}")
            yield test_db

        finally:
            # Cleanup
            self._drop_database(test_db_name)
            self.logger.info(f"Cleaned up test database: {test_db_name}")

    def _create_database(self, db_name: str):
        """Create test database."""
        import psycopg2

        try:
            # Connect to postgres database to create test db
            conn = psycopg2.connect(
                host=self.base_config.host,
                port=self.base_config.port,
                database="postgres",
                user=self.base_config.user,
                password=self.base_config.password
            )

            conn.autocommit = True
            with conn.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE {db_name}")
                self.logger.debug(f"Created test database: {db_name}")

            conn.close()

        except Exception as e:
            self.logger.error(f"Failed to create test database {db_name}: {e}")
            raise

    def _drop_database(self, db_name: str):
        """Drop test database."""
        import psycopg2

        try:
            # Connect to postgres database to drop test db
            conn = psycopg2.connect(
                host=self.base_config.host,
                port=self.base_config.port,
                database="postgres",
                user=self.base_config.user,
                password=self.base_config.password
            )

            conn.autocommit = True
            with conn.cursor() as cursor:
                # Terminate active connections first
                cursor.execute(f"""
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = '{db_name}'
                """)
                cursor.execute(f"DROP DATABASE IF EXISTS {db_name}")
                self.logger.debug(f"Dropped test database: {db_name}")

            conn.close()

        except Exception as e:
            self.logger.warning(f"Failed to drop test database {db_name}: {e}")

    def _load_schema(self, db_manager: DatabaseManager, schema_file: Path):
        """Load database schema from file."""
        try:
            schema_sql = schema_file.read_text()

            with db_manager.connection.get_cursor() as cursor:
                cursor.execute(schema_sql)
                db_manager.connection.connection.commit()

            self.logger.debug(f"Loaded schema from: {schema_file}")

        except Exception as e:
            self.logger.error(f"Failed to load schema: {e}")
            raise

    def _seed_test_data(self, db_manager: DatabaseManager):
        """Seed test database with sample data."""
        try:
            # Sample market data
            test_market_data = [
                {
                    "symbol": "AAPL",
                    "timestamp": "2024-01-01 09:30:00",
                    "open": 185.00,
                    "high": 186.50,
                    "low": 184.50,
                    "close": 186.00,
                    "volume": 1000000,
                    "source": "test"
                },
                {
                    "symbol": "AAPL",
                    "timestamp": "2024-01-01 10:00:00",
                    "open": 186.00,
                    "high": 187.00,
                    "low": 185.00,
                    "close": 186.50,
                    "volume": 800000,
                    "source": "test"
                },
                {
                    "symbol": "MSFT",
                    "timestamp": "2024-01-01 09:30:00",
                    "open": 380.00,
                    "high": 382.00,
                    "low": 378.00,
                    "close": 381.00,
                    "volume": 500000,
                    "source": "test"
                }
            ]

            # Insert market data
            for data in test_market_data:
                db_manager.insert_market_data(data)

            # Sample trading signals
            test_signals = [
                {
                    "symbol": "AAPL",
                    "strategy_name": "test_rsi",
                    "signal_type": "BUY",
                    "confidence": 0.85,
                    "timestamp": "2024-01-01 10:30:00",
                    "price": 186.50,
                    "metadata": {"rsi": 30, "threshold": 30}
                },
                {
                    "symbol": "MSFT",
                    "strategy_name": "test_ma",
                    "signal_type": "SELL",
                    "confidence": 0.75,
                    "timestamp": "2024-01-01 11:00:00",
                    "price": 380.00,
                    "metadata": {"fast_ma": 382, "slow_ma": 380}
                }
            ]

            # Insert signals
            for signal in test_signals:
                db_manager.insert_trading_signal(signal)

            # Sample backtest results
            test_backtest = {
                "strategy_name": "test_combined",
                "symbol": "AAPL",
                "start_date": "2024-01-01",
                "end_date": "2024-01-02",
                "total_return": 0.025,
                "sharpe_ratio": 1.5,
                "max_drawdown": 0.05,
                "win_rate": 0.65,
                "total_trades": 10,
                "parameters": {"rsi_period": 14, "ma_period": 20}
            }

            db_manager.insert_backtest_result(test_backtest)

            self.logger.debug("Seeded test database with sample data")

        except Exception as e:
            self.logger.error(f"Failed to seed test data: {e}")
            raise


class TestDataGenerator:
    """Generate realistic test data for various scenarios."""

    def __init__(self):
        self.logger = get_nexus_logger("test.generator")

    def generate_market_data(self, symbol: str, days: int = 30,
                           base_price: float = 100.0,
                           volatility: float = 0.02) -> list:
        """Generate realistic market data."""
        import random
        from datetime import datetime, timedelta

        data = []
        current_price = base_price
        start_date = datetime.now() - timedelta(days=days)

        for i in range(days):
            date = start_date + timedelta(days=i)
            if date.weekday() >= 5:  # Skip weekends
                continue

            # Generate OHLC with realistic volatility
            open_price = current_price
            high_change = random.uniform(0, volatility)
            low_change = random.uniform(-volatility, 0)
            close_change = random.uniform(-volatility, volatility)

            high = open_price * (1 + high_change)
            low = open_price * (1 + low_change)
            close = open_price * (1 + close_change)

            # Ensure OHLC relationships
            high = max(high, open_price, close)
            low = min(low, open_price, close)

            volume = random.randint(500000, 2000000)

            data.append({
                "symbol": symbol,
                "timestamp": date.strftime("%Y-%m-%d %H:%M:%S"),
                "open": round(open_price, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(close, 2),
                "volume": volume,
                "source": "generated"
            })

            current_price = close

        return data

    def generate_trading_signals(self, symbol: str, signals_count: int = 10) -> list:
        """Generate sample trading signals."""
        import random
        from datetime import datetime, timedelta

        strategies = ["rsi_divergence", "ma_crossover", "volume_breakout", "momentum"]
        signal_types = ["BUY", "SELL"]

        signals = []
        base_date = datetime.now() - timedelta(days=30)

        for i in range(signals_count):
            date = base_date + timedelta(days=random.randint(0, 30))
            signals.append({
                "symbol": symbol,
                "strategy_name": random.choice(strategies),
                "signal_type": random.choice(signal_types),
                "confidence": round(random.uniform(0.5, 0.95), 2),
                "timestamp": date.strftime("%Y-%m-%d %H:%M:%S"),
                "price": round(random.uniform(80, 120), 2),
                "metadata": {
                    "indicator_value": round(random.uniform(20, 80), 1),
                    "threshold": 50
                }
            })

        return signals


# Global test manager instance
_test_manager: Optional[TestDatabaseManager] = None

def get_test_database_manager() -> TestDatabaseManager:
    """Get global test database manager instance."""
    global _test_manager
    if _test_manager is None:
        _test_manager = TestDatabaseManager()
    return _test_manager

@contextmanager
def test_database(schema_file: Optional[Path] = None) -> Generator[DatabaseManager, None, None]:
    """Context manager for test database."""
    manager = get_test_database_manager()
    with manager.create_test_database(schema_file) as db:
        yield db

# CLI utilities
def main():
    """CLI interface for test database operations."""
    import argparse

    parser = argparse.ArgumentParser(description="NEXUS Test Database Utilities")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Create test database
    create_parser = subparsers.add_parser("create", help="Create test database")
    create_parser.add_argument("--schema", help="Schema file to load")

    # Generate test data
    gen_parser = subparsers.add_parser("generate", help="Generate test data")
    gen_parser.add_argument("type", choices=["market", "signals"], help="Data type to generate")
    gen_parser.add_argument("--symbol", default="TEST", help="Symbol for data")
    gen_parser.add_argument("--count", type=int, default=100, help="Number of records")

    args = parser.parse_args()

    if args.command == "create":
        schema_path = Path(args.schema) if args.schema else None
        manager = get_test_database_manager()

        with manager.create_test_database(schema_path) as db:
            print(f"✅ Created test database: {db.config.database}")
            print("Run your tests, database will be cleaned up automatically")

            # Keep alive until user interrupts
            try:
                input("Press Enter to cleanup test database...")
            except KeyboardInterrupt:
                pass

    elif args.command == "generate":
        generator = TestDataGenerator()

        if args.type == "market":
            data = generator.generate_market_data(args.symbol, days=min(args.count // 5, 365))
            print(f"Generated {len(data)} market data records for {args.symbol}")
            for record in data[:5]:  # Show first 5
                print(f"  {record['timestamp']}: {record['close']}")
        elif args.type == "signals":
            data = generator.generate_trading_signals(args.symbol, args.count)
            print(f"Generated {len(data)} trading signals for {args.symbol}")
            for signal in data[:5]:  # Show first 5
                print(f"  {signal['timestamp']}: {signal['signal_type']} @ {signal['price']}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
