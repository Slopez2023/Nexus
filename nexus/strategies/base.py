"""Base classes and core types for trading strategies.

This module defines the fundamental building blocks for all trading strategies
in the NEXUS system. All components follow professional best practices with
full type safety, comprehensive validation, and enterprise-grade error handling.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List, Literal, Optional, Protocol
import logging

logger = logging.getLogger(__name__)


# Exception Hierarchy
class StrategyError(Exception):
    """Base exception for all strategy-related errors."""

    pass


class ParameterError(StrategyError):
    """Raised when strategy parameters are invalid."""

    pass


class SignalError(StrategyError):
    """Raised when signal generation fails."""

    pass


class ValidationError(StrategyError):
    """Raised when validation fails."""

    pass


# Protocols
class MarketData(Protocol):
    """Protocol for market data interface.

    Strategies use this interface to access market data without
    depending on specific implementations.
    """

    def get_price(self, symbol: str) -> float:
        """Get current price for symbol."""
        ...

    def get_volume(self, symbol: str) -> int:
        """Get current volume for symbol."""
        ...

    def get_historical_data(self, symbol: str, days: int) -> List[Dict[str, Any]]:
        """Get historical data for symbol."""
        ...


# Core Data Structures
@dataclass(frozen=True)
class TradeSignal:
    """Immutable trading signal with comprehensive metadata.

    This is the atomic unit of trading decisions. Immutable for thread safety,
    serialization, and caching. All signals must pass validation at creation.

    Attributes:
        symbol: Trading symbol (e.g., 'AAPL', 'BTC/USD')
        timestamp: Signal generation timestamp (UTC)
        direction: Trade direction ('long' or 'short')
        confidence: Signal confidence score (0.0 to 1.0)
        reasoning: Human-readable explanation for the signal
        metadata: Additional strategy-specific data (serializable)
    """

    symbol: str
    timestamp: datetime
    direction: Literal["long", "short"]
    confidence: float
    reasoning: str
    metadata: Dict[str, Any]

    def __post_init__(self) -> None:
        """Validate signal integrity at creation time.

        Raises:
            ValueError: If any validation fails
        """
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError(f"Invalid symbol: {self.symbol!r}")

        if not isinstance(self.timestamp, datetime):
            raise ValueError(f"Invalid timestamp: {self.timestamp!r}")

        if self.direction not in ["long", "short"]:
            raise ValueError(
                f"Invalid direction: {self.direction!r}. Must be 'long' or 'short'"
            )

        if not isinstance(self.confidence, (int, float)) or not (
            0.0 <= self.confidence <= 1.0
        ):
            raise ValueError(f"Confidence must be 0.0-1.0: {self.confidence!r}")

        if not isinstance(self.reasoning, str) or not self.reasoning.strip():
            raise ValueError(
                f"Reasoning required and must be non-empty: {self.reasoning!r}"
            )

        if not isinstance(self.metadata, dict):
            raise ValueError(f"Metadata must be dict: {type(self.metadata)!r}")

        # Signal created successfully

    @property
    def is_high_confidence(self) -> bool:
        """Check if signal meets high confidence threshold (>= 0.8)."""
        return self.confidence >= 0.8

    @property
    def is_low_confidence(self) -> bool:
        """Check if signal meets low confidence threshold (<= 0.2)."""
        return self.confidence <= 0.2

    def to_dict(self) -> Dict[str, Any]:
        """Serialize signal to dictionary for storage/transmission.

        Returns:
            Dictionary representation with ISO timestamp
        """
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "direction": self.direction,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TradeSignal":
        """Deserialize signal from dictionary.

        Args:
            data: Dictionary with signal data

        Returns:
            TradeSignal instance

        Raises:
            ValueError: If data is invalid
        """
        try:
            return cls(
                symbol=data["symbol"],
                timestamp=datetime.fromisoformat(data["timestamp"]),
                direction=data["direction"],
                confidence=data["confidence"],
                reasoning=data["reasoning"],
                metadata=data["metadata"],
            )
        except KeyError as e:
            raise ValueError(f"Missing required field: {e}") from e
        except ValueError as e:
            raise ValueError(f"Invalid data format: {e}") from e


@dataclass
class ParameterSpec:
    """Parameter specification with bounds and validation.

    Defines valid ranges and types for strategy parameters.
    Used for runtime validation and configuration management.
    """

    name: str
    type: Literal["int", "float", "str", "bool"]
    default: Any
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    choices: Optional[List[Any]] = None
    description: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate parameter spec."""
        if not isinstance(self.name, str) or not self.name:
            raise ValueError(f"Invalid parameter name: {self.name!r}")

        valid_types = ["int", "float", "str", "bool"]
        if self.type not in valid_types:
            raise ValueError(
                f"Invalid type: {self.type!r}. Must be one of {valid_types}"
            )

        if self.min_value is not None and self.max_value is not None:
            if self.min_value >= self.max_value:
                raise ValueError("min_value must be < max_value")

    def validate(self, value: Any) -> bool:
        """Validate a parameter value against this spec.

        Args:
            value: Value to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            # Type checking
            if self.type == "int":
                if not isinstance(value, int):
                    return False
            elif self.type == "float":
                if not isinstance(value, (int, float)):
                    return False
            elif self.type == "str":
                if not isinstance(value, str):
                    return False
            elif self.type == "bool":
                if not isinstance(value, bool):
                    return False

            # Range checking
            if self.min_value is not None and value < self.min_value:
                return False
            if self.max_value is not None and value > self.max_value:
                return False

            # Choices checking
            if self.choices is not None and value not in self.choices:
                return False

            return True
        except Exception:
            return False


@dataclass
class StrategyMetadata:
    """Comprehensive strategy information for management and discovery.

    Provides all information needed to understand, configure, and manage
    a trading strategy without instantiating it.
    """

    name: str
    description: str
    version: str
    parameters: Dict[str, ParameterSpec]
    risk_profile: Dict[str, Any]  # Could be more structured later
    tags: List[str]
    author: Optional[str] = None
    created_date: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Validate metadata."""
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError(f"Invalid name: {self.name!r}")

        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError(f"Invalid description: {self.description!r}")

        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError(f"Invalid version: {self.version!r}")

        if not isinstance(self.parameters, dict):
            raise ValueError(f"Parameters must be dict: {type(self.parameters)!r}")

        for param_name, param_spec in self.parameters.items():
            if not isinstance(param_spec, ParameterSpec):
                raise ValueError(f"Parameter {param_name} must be ParameterSpec")

    def validate_parameters(self, params: Dict[str, Any]) -> List[str]:
        """Validate parameter dictionary against specs.

        Args:
            params: Parameters to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Check required parameters
        for param_name, param_spec in self.parameters.items():
            if param_name not in params:
                errors.append(f"Missing required parameter: {param_name}")
            else:
                if not param_spec.validate(params[param_name]):
                    errors.append(
                        f"Invalid value for {param_name}: {params[param_name]!r}"
                    )

        # Check for extra parameters
        extra_params = set(params.keys()) - set(self.parameters.keys())
        if extra_params:
            errors.append(f"Unexpected parameters: {list(extra_params)}")

        return errors


class BaseStrategy(ABC):
    """Abstract base class for all trading strategies.

    This class defines the contract that all strategies must implement.
    It enforces type safety, validation, and consistent interfaces.

    Key Principles:
    - Stateless: All state in parameters (deterministic)
    - Validated: Parameters checked at initialization
    - Documented: Clear interfaces and error messages
    - Logged: All operations logged for debugging
    """

    def __init__(self, **parameters: Any) -> None:
        """Initialize strategy with validated parameters.

        Args:
            **parameters: Strategy-specific parameters

        Raises:
            ParameterError: If parameters are invalid
        """
        self._parameters = parameters.copy()
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Validate parameters
        self._validate_parameters()

        # Strategy initialized

    @abstractmethod
    def generate_signals(self, market_data: MarketData) -> List[TradeSignal]:
        """Generate trading signals from current market data.

        This is the core method that strategies implement. Should be:
        - Deterministic (same inputs = same outputs)
        - Efficient (no unnecessary computations)
        - Well-logged (debug level for signal generation)

        Args:
            market_data: Current market data interface

        Returns:
            List of trading signals (can be empty)

        Raises:
            SignalError: If signal generation fails
        """
        pass

    @abstractmethod
    def validate_parameters(self) -> bool:
        """Validate that current parameters are within acceptable bounds.

        Called during initialization and parameter updates.
        Should check all parameter constraints.

        Returns:
            True if parameters are valid

        Raises:
            ParameterError: If parameters are invalid (implementation choice)
        """
        pass

    @property
    @abstractmethod
    def metadata(self) -> StrategyMetadata:
        """Return strategy metadata for management and discovery.

        Should return a StrategyMetadata instance with complete information
        about the strategy, its parameters, and risk profile.
        """
        pass

    def _validate_parameters(self) -> None:
        """Internal parameter validation called during init and updates."""
        try:
            if not self.validate_parameters():
                raise ParameterError(
                    f"Parameter validation failed for {self.__class__.__name__}"
                )
        except Exception as e:
            self._logger.error(f"Parameter validation error: {e}")
            raise ParameterError(f"Invalid parameters: {e}") from e

    def get_parameter(self, name: str, default: Any = None) -> Any:
        """Safely get parameter value.

        Args:
            name: Parameter name
            default: Default value if not found

        Returns:
            Parameter value or default
        """
        return self._parameters.get(name, default)

    def set_parameter(self, name: str, value: Any) -> None:
        """Update parameter with validation.

        Args:
            name: Parameter name
            value: New value

        Raises:
            ParameterError: If new value is invalid
        """
        old_value = self._parameters.get(name)
        self._parameters[name] = value

        try:
            self._validate_parameters()
            self._logger.info(f"Parameter updated: {name} = {value} (was {old_value})")
        except ParameterError:
            # Rollback on validation failure
            self._parameters[name] = old_value
            self._logger.warning(f"Parameter update rejected: {name} = {value}")
            raise

    def get_parameters(self) -> Dict[str, Any]:
        """Get all current parameters."""
        return self._parameters.copy()

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"{self.__class__.__name__}({self._parameters})"
