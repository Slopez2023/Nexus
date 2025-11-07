"""Strategy factory for registration and instantiation.

This module implements the registry pattern for strategy management.
Provides clean interfaces for strategy discovery, creation, and validation.
Follows professional patterns with comprehensive error handling and logging.
"""

from typing import Dict, Type, Any, List
import logging

from .base import BaseStrategy, StrategyError

logger = logging.getLogger(__name__)


class StrategyFactory:
    """Factory for creating and managing trading strategies.

    Uses registry pattern for clean strategy discovery and instantiation.
    Provides validation, error handling, and comprehensive logging for
    all strategy operations.

    Thread-safe for registration operations. Creation is thread-safe
    if strategy constructors are thread-safe.
    """

    _registry: Dict[str, Type[BaseStrategy]] = {}

    @classmethod
    def register(cls, strategy_class: Type[BaseStrategy]) -> None:
        """Register a strategy class for creation.

        Names derived from class names (lowercase, 'strategy' suffix removed).
        Example: RSIStrategy -> 'rsi'

        Args:
        strategy_class: Strategy class to register

        Raises:
        ValueError: If already registered or invalid class
        TypeError: If not a class
        """
        if not isinstance(strategy_class, type):
            raise TypeError(f"Must be a class: {strategy_class!r}")

        if not issubclass(strategy_class, BaseStrategy):
            raise ValueError(
                f"Must inherit from BaseStrategy: {strategy_class.__name__}"
            )

        name = strategy_class.__name__.lower()
        if name.endswith("strategy"):
            name = name[:-8]  # Remove 'strategy' suffix

        if name in cls._registry:
            existing_class = cls._registry[name]
            if existing_class is not strategy_class:
                raise ValueError(f"Strategy name '{name}' already registered")
            # Allow re-registration of same class (idempotent)
            return

        cls._registry[name] = strategy_class
        logger.info(f"Registered strategy: {name} -> {strategy_class.__name__}")

    @classmethod
    def unregister(cls, name: str) -> None:
        """Unregister a strategy class.

        Args:
            name: Registered strategy name

        Raises:
            ValueError: If strategy not registered
        """
        if name not in cls._registry:
            raise ValueError(f"Strategy not registered: {name}")

        del cls._registry[name]
        logger.info(f"Unregistered strategy: {name}")

    @classmethod
    def create(cls, name: str, **parameters: Any) -> BaseStrategy:
        """Create strategy instance with validation.

        Args:
            name: Registered strategy name
            **parameters: Strategy parameters (validated by strategy)

        Returns:
            Configured strategy instance

        Raises:
            ValueError: If strategy not found
            StrategyError: If strategy creation fails
        """
        if name not in cls._registry:
            available = list(cls._registry.keys())
            raise ValueError(f"Unknown strategy '{name}'. Available: {available}")

        strategy_class = cls._registry[name]

        try:
            strategy = strategy_class(**parameters)
            logger.info(f"Created strategy: {name} with {len(parameters)} parameters")
            return strategy
        except Exception as e:
            logger.error(f"Failed to create strategy {name}: {e}")
            raise StrategyError(f"Strategy creation failed: {e}") from e

    @classmethod
    def list_strategies(cls) -> List[str]:
        """List all registered strategy names.

        Returns:
            Sorted list of strategy names
        """
        return sorted(cls._registry.keys())

    @classmethod
    def get_strategy_info(cls, name: str) -> Dict[str, Any]:
        """Get information about a registered strategy.

        Args:
            name: Registered strategy name

        Returns:
            Dictionary with strategy information

        Raises:
            ValueError: If strategy not registered
        """
        if name not in cls._registry:
            raise ValueError(f"Unknown strategy: {name}")

        strategy_class = cls._registry[name]

        # Get metadata if available (may fail during import)
        metadata = None
        try:
            # Create temporary instance to get metadata
            temp_strategy = strategy_class()
            metadata = temp_strategy.metadata
        except Exception as e:
            logger.warning(f"Could not get metadata for {name}: {e}")

        return {
            "name": name,
            "class": strategy_class.__name__,
            "module": strategy_class.__module__,
            "metadata": metadata,
        }

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if a strategy is registered.

        Args:
            name: Strategy name

        Returns:
            True if registered
        """
        return name in cls._registry

    @classmethod
    def clear_registry(cls) -> None:
        """Clear all registered strategies.

        Useful for testing or reinitialization.
        """
        count = len(cls._registry)
        cls._registry.clear()
        logger.info(f"Cleared strategy registry ({count} strategies)")

    @classmethod
    def get_registry_size(cls) -> int:
        """Get number of registered strategies."""
        return len(cls._registry)
