# 🏗️ Phase 2.1.1: Core Framework Implementation - PROFESSIONAL BEST PRACTICES

## 🚨 PROFESSIONAL MANDATE

**You are building enterprise-grade software. Act like it. No excuses, no shortcuts.**

This implementation follows industry best practices for Python development. Every line of code must be:
- Type-safe with full hints
- Tested with TDD approach
- Documented with Google-style docstrings
- Following SOLID principles
- Performance-optimized
- Error-handling robust
- Quant-ready with statistical rigor

## 🎯 Implementation Objectives

**Deliver production-ready strategy framework that:**
- Prevents runtime errors through type safety
- Enables comprehensive testing and validation
- Provides clean interfaces for all future strategies
- Scales to unlimited strategy types
- Maintains professional code quality standards

## 📋 Development Methodology

### TDD (Test-Driven Development)
**Write tests BEFORE implementation. Every feature starts with a failing test.**

1. **Red**: Write failing test that defines expected behavior
2. **Green**: Implement minimal code to pass test
3. **Refactor**: Clean code while maintaining passing tests
4. **Repeat**: No code without tests

### Clean Code Principles
- **Single Responsibility**: Each class/method does one thing
- **Open/Closed**: Extensible without modification
- **Liskov Substitution**: Subtypes replace base types
- **Interface Segregation**: Small, focused interfaces
- **Dependency Inversion**: Depend on abstractions

### Code Standards
- **PEP 8**: Strict compliance
- **Type Hints**: Full type annotations everywhere
- **Docstrings**: Google-style for all public APIs
- **Naming**: snake_case functions, PascalCase classes
- **Imports**: Absolute imports, grouped by stdlib/external/internal

## 🏛️ Implementation Plan

### Step 1: Environment Setup (1 hour)
**Set up professional development environment.**

```bash
# Enable strict mypy
echo "[tool.mypy]" >> pyproject.toml
echo "strict = true" >> pyproject.toml
echo "disallow_untyped_defs = true" >> pyproject.toml

# Configure pytest with coverage
pytest --cov=nexus --cov-report=html --cov-fail-under=95
```

### Step 2: TradeSignal Implementation (2 hours)
**Immutable signal representation with full validation.**

**File: `nexus/strategies/base.py`**

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Literal
import logging

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class TradeSignal:
    """Immutable trading signal with comprehensive metadata.

    This is the atomic unit of trading decisions. Immutable for thread safety,
    serialization, and caching.

    Attributes:
        symbol: Trading symbol (e.g., 'AAPL', 'BTC/USD')
        timestamp: Signal generation timestamp (UTC)
        direction: Trade direction ('long' or 'short')
        confidence: Signal confidence score (0.0 to 1.0)
        reasoning: Human-readable explanation for the signal
        metadata: Additional strategy-specific data
    """
    symbol: str
    timestamp: datetime
    direction: Literal["long", "short"]
    confidence: float
    reasoning: str
    metadata: Dict[str, Any]

    def __post_init__(self) -> None:
        """Validate signal integrity at creation time."""
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError(f"Invalid symbol: {self.symbol}")

        if not isinstance(self.timestamp, datetime):
            raise ValueError(f"Invalid timestamp: {self.timestamp}")

        if self.direction not in ["long", "short"]:
            raise ValueError(f"Invalid direction: {self.direction}")

        if not isinstance(self.confidence, (int, float)) or not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Confidence must be 0.0-1.0: {self.confidence}")

        if not isinstance(self.reasoning, str) or not self.reasoning.strip():
            raise ValueError(f"Reasoning required: {self.reasoning}")

        if not isinstance(self.metadata, dict):
            raise ValueError(f"Metadata must be dict: {self.metadata}")

        logger.debug(f"TradeSignal created: {self.symbol} {self.direction} conf={self.confidence}")

    @property
    def is_high_confidence(self) -> bool:
        """Check if signal meets high confidence threshold."""
        return self.confidence >= 0.8

    def to_dict(self) -> Dict[str, Any]:
        """Serialize signal to dictionary for storage/transmission."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "direction": self.direction,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TradeSignal':
        """Deserialize signal from dictionary."""
        return cls(
            symbol=data["symbol"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            direction=data["direction"],
            confidence=data["confidence"],
            reasoning=data["reasoning"],
            metadata=data["metadata"]
        )
```

**Tests First (TDD):**
```python
# tests/strategies/test_base.py
import pytest
from datetime import datetime
from nexus.strategies.base import TradeSignal

class TestTradeSignal:
    def test_valid_signal_creation(self):
        signal = TradeSignal(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 1, 12, 0),
            direction="long",
            confidence=0.85,
            reasoning="RSI oversold",
            metadata={"rsi": 25.5}
        )
        assert signal.symbol == "AAPL"
        assert signal.direction == "long"
        assert signal.confidence == 0.85

    def test_invalid_confidence(self):
        with pytest.raises(ValueError, match="Confidence must be 0.0-1.0"):
            TradeSignal(
                symbol="AAPL",
                timestamp=datetime.now(),
                direction="long",
                confidence=1.5,  # Invalid
                reasoning="Test",
                metadata={}
            )

    def test_immutability(self):
        signal = TradeSignal(
            symbol="AAPL",
            timestamp=datetime.now(),
            direction="long",
            confidence=0.8,
            reasoning="Test",
            metadata={}
        )
        with pytest.raises(AttributeError):
            signal.confidence = 0.9  # Should fail - frozen

    def test_serialization(self):
        signal = TradeSignal(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 1, 12, 0),
            direction="long",
            confidence=0.85,
            reasoning="RSI oversold",
            metadata={"rsi": 25.5}
        )
        data = signal.to_dict()
        restored = TradeSignal.from_dict(data)
        assert signal == restored
```

### Step 3: BaseStrategy Implementation (3 hours)
**Abstract interface with proper inheritance.**

```python
from abc import ABC, abstractmethod
from typing import List, Protocol
import logging

logger = logging.getLogger(__name__)

class MarketData(Protocol):
    """Protocol for market data interface."""
    def get_price(self, symbol: str) -> float: ...
    def get_volume(self, symbol: str) -> int: ...
    def get_historical_data(self, symbol: str, days: int) -> List[Dict]: ...

class BaseStrategy(ABC):
    """Abstract base class for all trading strategies.

    This class defines the contract that all strategies must implement.
    It enforces type safety, validation, and consistent interfaces.

    Strategies should be:
    - Stateless (all state in parameters)
    - Deterministic (same inputs = same outputs)
    - Well-documented with clear logic
    """

    def __init__(self, **parameters):
        """Initialize strategy with validated parameters."""
        self._parameters = parameters
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._validate_parameters()
        self._logger.info(f"Strategy initialized: {self.__class__.__name__}")

    @abstractmethod
    def generate_signals(self, market_data: MarketData) -> List[TradeSignal]:
        """Generate trading signals from current market data.

        This is the core method that strategies implement.

        Args:
            market_data: Current market data interface

        Returns:
            List of trading signals (can be empty)

        Raises:
            StrategyError: If signal generation fails
        """
        pass

    @abstractmethod
    def validate_parameters(self) -> bool:
        """Validate that current parameters are within acceptable bounds.

        Returns:
            True if parameters are valid

        Raises:
            ParameterError: If parameters are invalid
        """
        pass

    @property
    @abstractmethod
    def metadata(self) -> StrategyMetadata:
        """Return strategy metadata for management and discovery."""
        pass

    def _validate_parameters(self) -> None:
        """Internal parameter validation called during init."""
        if not self.validate_parameters():
            raise ParameterError(f"Invalid parameters for {self.__class__.__name__}")

    def get_parameter(self, name: str, default: Any = None) -> Any:
        """Safely get parameter value."""
        return self._parameters.get(name, default)

    def set_parameter(self, name: str, value: Any) -> None:
        """Update parameter with validation."""
        old_value = self._parameters.get(name)
        self._parameters[name] = value
        try:
            self._validate_parameters()
            self._logger.info(f"Parameter {name}: {old_value} -> {value}")
        except ParameterError:
            # Rollback on validation failure
            self._parameters[name] = old_value
            raise
```

### Step 4: StrategyFactory Implementation (2 hours)
**Registry pattern with validation and error handling.**

```python
from typing import Dict, Type, Any
import logging

logger = logging.getLogger(__name__)

class StrategyFactory:
    """Factory for creating and managing trading strategies.

    Uses registry pattern for clean strategy discovery and instantiation.
    Provides validation and error handling for all strategy operations.
    """

    _registry: Dict[str, Type[BaseStrategy]] = {}

    @classmethod
    def register(cls, strategy_class: Type[BaseStrategy]) -> None:
        """Register a strategy class for creation.

        Args:
            strategy_class: Strategy class to register

        Raises:
            ValueError: If strategy already registered or invalid
        """
        name = strategy_class.__name__.lower().replace('strategy', '')

        if name in cls._registry:
            raise ValueError(f"Strategy already registered: {name}")

        if not issubclass(strategy_class, BaseStrategy):
            raise ValueError(f"Must inherit from BaseStrategy: {strategy_class}")

        cls._registry[name] = strategy_class
        logger.info(f"Registered strategy: {name} -> {strategy_class}")

    @classmethod
    def unregister(cls, name: str) -> None:
        """Unregister a strategy class."""
        if name in cls._registry:
            del cls._registry[name]
            logger.info(f"Unregistered strategy: {name}")

    @classmethod
    def create(cls, name: str, **parameters) -> BaseStrategy:
        """Create strategy instance with validation.

        Args:
            name: Registered strategy name
            **parameters: Strategy parameters

        Returns:
            Configured strategy instance

        Raises:
            ValueError: If strategy not found
            ParameterError: If parameters invalid
        """
        if name not in cls._registry:
            available = list(cls._registry.keys())
            raise ValueError(f"Unknown strategy '{name}'. Available: {available}")

        strategy_class = cls._registry[name]

        try:
            strategy = strategy_class(**parameters)
            logger.info(f"Created strategy: {name} with params {parameters}")
            return strategy
        except Exception as e:
            logger.error(f"Failed to create strategy {name}: {e}")
            raise StrategyError(f"Strategy creation failed: {e}") from e

    @classmethod
    def list_strategies(cls) -> List[str]:
        """List all registered strategy names."""
        return list(cls._registry.keys())

    @classmethod
    def get_strategy_info(cls, name: str) -> Dict[str, Any]:
        """Get information about a registered strategy."""
        if name not in cls._registry:
            raise ValueError(f"Unknown strategy: {name}")

        strategy_class = cls._registry[name]
        return {
            "name": name,
            "class": strategy_class.__name__,
            "module": strategy_class.__module__,
            "metadata": strategy_class.metadata if hasattr(strategy_class, 'metadata') else None
        }
```

### Step 5: Exception Classes (1 hour)
**Professional error handling hierarchy.**

```python
class StrategyError(Exception):
    """Base exception for strategy-related errors."""
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
```

### Step 6: Comprehensive Testing (4 hours)
**100% test coverage with edge cases.**

```python
# Test strategy factory
class TestStrategyFactory:
    def test_register_valid_strategy(self):
        class TestStrategy(BaseStrategy):
            def generate_signals(self, market_data):
                return []
            def validate_parameters(self):
                return True
            @property
            def metadata(self):
                return StrategyMetadata(...)

        StrategyFactory.register(TestStrategy)
        assert "test" in StrategyFactory.list_strategies()

    def test_register_duplicate_strategy(self):
        with pytest.raises(ValueError, match="already registered"):
            StrategyFactory.register(TestStrategy)
            StrategyFactory.register(TestStrategy)

    def test_create_unknown_strategy(self):
        with pytest.raises(ValueError, match="Unknown strategy"):
            StrategyFactory.create("nonexistent")

    def test_create_with_invalid_params(self):
        # Mock strategy that fails validation
        with pytest.raises(ParameterError):
            StrategyFactory.create("test", invalid_param=True)
```

### Step 7: Documentation & Type Checking (2 hours)
**Complete Google-style docstrings and strict mypy compliance.**

```bash
# Run type checking
mypy nexus/strategies/ --strict --disallow-untyped-defs

# Generate documentation
sphinx-build docs/ docs/_build/html
```

### Step 8: Performance Benchmarking (1 hour)
**Ensure framework doesn't introduce bottlenecks.**

```python
# benchmarks/test_performance.py
def test_signal_creation_performance(benchmark):
    def create_signals():
        signals = []
        for i in range(1000):
            signals.append(TradeSignal(
                symbol=f"TEST{i}",
                timestamp=datetime.now(),
                direction="long" if i % 2 == 0 else "short",
                confidence=0.5 + (i % 50) / 100,
                reasoning=f"Test signal {i}",
                metadata={"index": i}
            ))
        return signals

    result = benchmark(create_signals)
    assert len(result) == 1000
```

## 📊 Quality Gates

**Code must pass ALL checks before commit:**

```bash
# Linting
flake8 nexus/strategies/ --max-line-length=88 --extend-ignore=E203,W503

# Type checking
mypy nexus/strategies/ --strict

# Testing
pytest tests/strategies/ -v --cov=nexus.strategies --cov-fail-under=95

# Security
bandit nexus/strategies/

# Performance
python -m pytest benchmarks/ -v
```

## 🚨 Professional Standards Enforced

**No compromise on quality:**
- **Zero mypy errors** - Type safety is mandatory
- **95%+ test coverage** - Every line tested
- **Zero flake8 violations** - Code style perfect
- **All docstrings complete** - Documentation professional
- **Performance benchmarks pass** - No bottlenecks
- **Security scan clean** - No vulnerabilities

## 📈 Quant-Specific Considerations

**Statistical rigor from day one:**
- Signal confidence must be calibrated (not arbitrary)
- Parameter bounds based on economic intuition
- Error handling for market data anomalies
- Logging for debugging signal generation
- Metadata for backtest analysis

## ⏱️ Timeline & Milestones

**Phase 2.1.1 Complete When:**
- ✅ All core classes implemented with full type hints
- ✅ 100% test coverage with edge cases covered
- ✅ Mypy strict mode passes
- ✅ Documentation generated and complete
- ✅ Performance benchmarks meet targets
- ✅ Integration tests with mock market data pass
- ✅ Code review checklist completed

**Time Estimate:** 16 hours professional development

## 💡 Best Practices Applied

1. **TDD**: Tests define requirements, implementation validates
2. **Type Safety**: Full hints prevent runtime errors
3. **SOLID**: Single responsibility, open/closed principle
4. **Error Handling**: Custom exceptions with context
5. **Logging**: Structured logging for debugging
6. **Documentation**: Professional docstrings
7. **Performance**: Benchmarking prevents regressions
8. **Security**: Input validation, no injection risks
9. **Testing**: Unit + integration + performance tests
10. **Code Review**: Self-review before commit

**This is how enterprise software is built. No shortcuts, no excuses.**
