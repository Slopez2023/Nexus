"""Enhanced logging configuration for NEXUS.

Provides structured logging with rotation, multiple levels, and JSON formatting
for production monitoring and debugging.
"""

import os
import json
import logging
import logging.handlers
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Create base log entry
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields from record
        if hasattr(record, 'props'):
            log_entry.update(record.props)

        return json.dumps(log_entry, default=str)


class NexusLogger:
    """Enhanced logger with multiple handlers and rotation."""

    def __init__(self, name: str = "nexus"):
        self.name = name
        self.logger = logging.getLogger(name)
        self._configured = False

    def configure(
        self,
        level: str = "INFO",
        log_dir: str = "logs",
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        console_level: Optional[str] = None,
        json_format: bool = False
    ) -> logging.Logger:
        """Configure logger with multiple handlers."""

        if self._configured:
            return self.logger

        # Convert string levels to logging levels
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }

        log_level = level_map.get(level.upper(), logging.INFO)
        console_log_level = level_map.get(console_level.upper() if console_level else level.upper(), log_level)

        # Clear existing handlers
        self.logger.handlers.clear()
        self.logger.setLevel(logging.DEBUG)  # Capture all levels, let handlers filter

        # Create logs directory
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)

        # Formatter
        if json_format:
            formatter = JSONFormatter()
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(console_log_level)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # General log file (rotating)
        general_handler = logging.handlers.RotatingFileHandler(
            log_path / "nexus.log",
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        general_handler.setLevel(log_level)
        general_handler.setFormatter(formatter)
        self.logger.addHandler(general_handler)

        # Error log file (rotating, ERROR and above only)
        error_handler = logging.handlers.RotatingFileHandler(
            log_path / "error.log",
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        self.logger.addHandler(error_handler)

        # Data operations log
        data_handler = logging.handlers.RotatingFileHandler(
            log_path / "data.log",
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        data_handler.setLevel(log_level)
        data_handler.setFormatter(formatter)
        data_handler.addFilter(lambda record: record.name.startswith("nexus.core.data"))
        self.logger.addHandler(data_handler)

        # Trading operations log
        trading_handler = logging.handlers.RotatingFileHandler(
            log_path / "trading.log",
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        trading_handler.setLevel(log_level)
        trading_handler.setFormatter(formatter)
        trading_handler.addFilter(lambda record: "trading" in record.name.lower() or "strategy" in record.name.lower())
        self.logger.addHandler(trading_handler)

        self._configured = True
        self.logger.info(f"NEXUS logging configured: level={level}, json={json_format}, dir={log_dir}")

        return self.logger


class LogContextManager:
    """Context manager for adding structured logging context."""

    def __init__(self, logger: logging.Logger, **context):
        self.logger = logger
        self.context = context
        self.old_factory = logging.getLogRecordFactory()

    def __enter__(self):
        def record_factory(*args, **kwargs):
            record = self.old_factory(*args, **kwargs)
            record.props = getattr(record, 'props', {})
            record.props.update(self.context)
            return record

        logging.setLogRecordFactory(record_factory)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.setLogRecordFactory(self.old_factory)


# Global logger instance
_nexus_logger: Optional[NexusLogger] = None

def get_nexus_logger(name: str = "nexus") -> logging.Logger:
    """Get configured NEXUS logger."""
    global _nexus_logger
    if _nexus_logger is None:
        _nexus_logger = NexusLogger()

    # Configure if not already done
    if not _nexus_logger._configured:
        _nexus_logger.configure(
            level=os.getenv("LOG_LEVEL", "INFO"),
            log_dir=os.getenv("LOG_DIR", "logs"),
            json_format=os.getenv("LOG_JSON", "false").lower() == "true",
            console_level=os.getenv("CONSOLE_LOG_LEVEL", "INFO")
        )

    return _nexus_logger.logger.getChild(name)

def setup_structured_logging(**context):
    """Context manager for adding structured logging context."""
    logger = get_nexus_logger()
    return LogContextManager(logger, **context)

# Convenience functions
def log_performance(operation: str, duration: float, **extra):
    """Log performance metrics."""
    logger = get_nexus_logger("performance")
    logger.info(f"Performance: {operation}", extra={
        "operation": operation,
        "duration_ms": duration * 1000,
        "duration_seconds": duration,
        **extra
    })

def log_error_with_context(error: Exception, operation: str, **context):
    """Log error with structured context."""
    logger = get_nexus_logger("error")
    logger.error(f"Error in {operation}: {str(error)}", extra={
        "operation": operation,
        "error_type": type(error).__name__,
        "error_message": str(error),
        **context
    })

def log_trading_signal(symbol: str, strategy: str, signal: str, confidence: float, **extra):
    """Log trading signals."""
    logger = get_nexus_logger("trading.signal")
    logger.info(f"Signal: {symbol} {signal} ({confidence:.2f}) via {strategy}", extra={
        "symbol": symbol,
        "strategy": strategy,
        "signal": signal,
        "confidence": confidence,
        **extra
    })

# Backwards compatibility
def get_logger(name: str = "nexus") -> logging.Logger:
    """Backwards compatible logger getter."""
    return get_nexus_logger(name)

def setup_logging(level: str = "INFO", log_file: str = "nexus.log") -> logging.Logger:
    """Backwards compatible logging setup."""
    logger = get_nexus_logger()
    return logger
