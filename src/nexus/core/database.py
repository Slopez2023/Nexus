"""Database connection and operations for NEXUS trading system.

Provides connection management, query execution, and data persistence
for PostgreSQL database with proper error handling and connection pooling.
"""

import os
import logging
from typing import Dict, List, Any, Optional
from contextlib import contextmanager
from dataclasses import dataclass

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor, Json


@dataclass
class DatabaseConfig:
    """Database configuration settings."""
    host: str = "localhost"
    port: int = 5432
    database: str = "nexus_trading"
    user: str = "nexus_user"
    password: str = ""
    min_connections: int = 1
    max_connections: int = 10

    @classmethod
    def from_env(cls) -> 'DatabaseConfig':
        """Create config from environment variables."""
        return cls(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "nexus_trading"),
            user=os.getenv("DB_USER", "nexus_user"),
            password=os.getenv("DB_PASSWORD", ""),
            min_connections=int(os.getenv("DB_MIN_CONNECTIONS", "1")),
            max_connections=int(os.getenv("DB_MAX_CONNECTIONS", "10"))
        )


class DatabaseConnection:
    """PostgreSQL database connection manager with connection pooling."""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._pool: Optional[pool.SimpleConnectionPool] = None
        self._initialize_pool()

    def _initialize_pool(self):
        """Initialize connection pool."""
        try:
            self._pool = pool.SimpleConnectionPool(
                minconn=self.config.min_connections,
                maxconn=self.config.max_connections,
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password
            )
            self.logger.info(f"Database connection pool initialized: {self.config.database}")
        except Exception as e:
            self.logger.error(f"Failed to initialize database pool: {e}")
            raise

    def close_all(self):
        """Close all connections in the pool."""
        if self._pool:
            self._pool.closeall()
            self.logger.info("Database connection pool closed")

    @contextmanager
    def get_connection(self):
        """Get a database connection from the pool."""
        conn = None
        try:
            conn = self._pool.getconn()
            yield conn
        except Exception as e:
            self.logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                self._pool.putconn(conn)

    @contextmanager
    def get_cursor(self):
        """Get a database cursor with automatic cleanup."""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                yield cursor
                conn.commit()
            except Exception as e:
                conn.rollback()
                self.logger.error(f"Database operation failed: {e}")
                raise
            finally:
                cursor.close()


class DatabaseManager:
    """High-level database operations for NEXUS."""

    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or DatabaseConfig.from_env()
        self.connection = DatabaseConnection(self.config)
        self.logger = logging.getLogger(__name__)

    def health_check(self) -> Dict[str, Any]:
        """Perform database health check."""
        try:
            with self.connection.get_cursor() as cursor:
                cursor.execute("SELECT COUNT(*) as table_count FROM information_schema.tables WHERE table_schema = 'public'")
                result = cursor.fetchone()
                return {
                    "status": "healthy",
                    "tables_count": result["table_count"],
                    "timestamp": "now()"
                }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": "now()"
            }

    # Market Data Operations
    def insert_market_data(self, data: Dict[str, Any]) -> int:
        """Insert market data record."""
        query = """
        INSERT INTO market_data (symbol, timestamp, open, high, low, close, volume, source)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """
        with self.connection.get_cursor() as cursor:
            cursor.execute(query, (
                data["symbol"],
                data["timestamp"],
                data.get("open"),
                data.get("high"),
                data.get("low"),
                data.get("close"),
                data.get("volume"),
                data.get("source", "unknown")
            ))
            return cursor.fetchone()["id"]

    def get_market_data(self, symbol: str, start_date: str, end_date: str,
                       limit: int = 1000) -> List[Dict[str, Any]]:
        """Retrieve market data for a symbol within date range."""
        query = """
        SELECT * FROM market_data
        WHERE symbol = %s AND timestamp BETWEEN %s AND %s
        ORDER BY timestamp DESC
        LIMIT %s
        """
        with self.connection.get_cursor() as cursor:
            cursor.execute(query, (symbol, start_date, end_date, limit))
            return [dict(row) for row in cursor.fetchall()]

    # Trading Signals Operations
    def insert_trading_signal(self, signal: Dict[str, Any]) -> int:
        """Insert trading signal."""
        query = """
        INSERT INTO trading_signals (symbol, strategy_name, signal_type, confidence,
                                   timestamp, price, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """
        with self.connection.get_cursor() as cursor:
            cursor.execute(query, (
                signal["symbol"],
                signal["strategy_name"],
                signal["signal_type"],
                signal.get("confidence"),
                signal["timestamp"],
                signal.get("price"),
                Json(signal.get("metadata", {}))
            ))
            return cursor.fetchone()["id"]

    def get_trading_signals(self, symbol: Optional[str] = None,
                           strategy: Optional[str] = None,
                           limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve trading signals with optional filters."""
        conditions = []
        params = []

        if symbol:
            conditions.append("symbol = %s")
            params.append(symbol)

        if strategy:
            conditions.append("strategy_name = %s")
            params.append(strategy)

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        query = f"""
        SELECT * FROM trading_signals
        WHERE {where_clause}
        ORDER BY timestamp DESC
        LIMIT %s
        """
        params.append(limit)

        with self.connection.get_cursor() as cursor:
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    # Backtest Results Operations
    def insert_backtest_result(self, result: Dict[str, Any]) -> int:
        """Insert backtest result."""
        query = """
        INSERT INTO backtest_results (strategy_name, symbol, start_date, end_date,
                                    total_return, sharpe_ratio, max_drawdown,
                                    win_rate, total_trades, parameters)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """
        with self.connection.get_cursor() as cursor:
            cursor.execute(query, (
                result["strategy_name"],
                result["symbol"],
                result["start_date"],
                result["end_date"],
                result.get("total_return"),
                result.get("sharpe_ratio"),
                result.get("max_drawdown"),
                result.get("win_rate"),
                result.get("total_trades"),
                Json(result.get("parameters", {}))
            ))
            return cursor.fetchone()["id"]

    def get_backtest_results(self, strategy: Optional[str] = None,
                           symbol: Optional[str] = None,
                           limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve backtest results."""
        conditions = []
        params = []

        if strategy:
            conditions.append("strategy_name = %s")
            params.append(strategy)

        if symbol:
            conditions.append("symbol = %s")
            params.append(symbol)

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        query = f"""
        SELECT * FROM backtest_results
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT %s
        """
        params.append(limit)

        with self.connection.get_cursor() as cursor:
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    # System Health Operations
    def insert_health_metric(self, component: str, status: str,
                           metric_name: Optional[str] = None,
                           metric_value: Optional[float] = None,
                           message: Optional[str] = None) -> int:
        """Insert system health metric."""
        query = """
        INSERT INTO system_health (component, status, metric_name, metric_value, message)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """
        with self.connection.get_cursor() as cursor:
            cursor.execute(query, (component, status, metric_name, metric_value, message))
            return cursor.fetchone()["id"]

    def get_health_metrics(self, component: Optional[str] = None,
                          status: Optional[str] = None,
                          limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve health metrics."""
        conditions = []
        params = []

        if component:
            conditions.append("component = %s")
            params.append(component)

        if status:
            conditions.append("status = %s")
            params.append(status)

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        query = f"""
        SELECT * FROM system_health
        WHERE {where_clause}
        ORDER BY timestamp DESC
        LIMIT %s
        """
        params.append(limit)

        with self.connection.get_cursor() as cursor:
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def cleanup_old_data(self, days_to_keep: int = 365):
        """Clean up old data (optional maintenance)."""
        self.logger.info(f"Cleaning up data older than {days_to_keep} days")

        # Archive old market data (keep last year)
        with self.connection.get_cursor() as cursor:
            cursor.execute("""
                DELETE FROM market_data
                WHERE timestamp < CURRENT_DATE - INTERVAL '%s days'
            """, (days_to_keep,))

            deleted_count = cursor.rowcount
            self.logger.info(f"Cleaned up {deleted_count} old market data records")


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None

def get_database_manager(config: Optional[DatabaseConfig] = None) -> DatabaseManager:
    """Get or create the global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(config)
    return _db_manager

def init_database() -> DatabaseManager:
    """Initialize database with default configuration."""
    # Set password from environment or use default for development
    os.environ.setdefault("DB_PASSWORD", "nexus_secure_2024!")

    config = DatabaseConfig.from_env()
    return get_database_manager(config)
