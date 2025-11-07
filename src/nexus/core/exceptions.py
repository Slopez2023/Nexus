"""Custom exceptions for NEXUS system."""


class NexusError(Exception):
    """Base exception for NEXUS system errors."""
    pass


class DataError(NexusError):
    """Raised when there's an issue with data fetching or validation."""
    pass


class ConfigurationError(NexusError):
    """Raised when there's a configuration-related error."""
    pass


class StrategyError(NexusError):
    """Raised when there's an issue with strategy execution."""
    pass


class RiskError(NexusError):
    """Raised when risk limits are violated."""
    pass


class ExecutionError(NexusError):
    """Raised when trade execution fails."""
    pass


class ValidationError(NexusError):
    """Raised when data or input validation fails."""
    pass
