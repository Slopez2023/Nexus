# 💻 NEXUS Code Style Guidelines

**Professional development standards for maintainable, collaborative trading system code.**

## 🎯 Philosophy

Code should be **understandable first**. We prioritize clarity over cleverness, consistency over personal preference, and maintainability over optimization (until proven necessary).

## 🐍 Python Standards

### Formatting
- **Formatter**: [Black](https://black.readthedocs.io/) with 88-character line length
- **Imports**: Grouped and sorted (stdlib, third-party, local)
- **Line Length**: 88 characters maximum
- **Quotes**: Double quotes for strings, single for characters

```python
# Good
import os
import sys

from typing import Dict, List, Optional
import pandas as pd
import numpy as np

from nexus.core.exceptions import NexusError
from .data import DataManager

def calculate_returns(prices: pd.Series,
                     method: str = "simple") -> pd.Series:
    """Calculate price returns."""
    if method == "simple":
        return prices.pct_change()
    elif method == "log":
        return np.log(prices / prices.shift(1))
    else:
        raise ValueError(f"Unknown method: {method}")

# Bad - inconsistent formatting, long lines
import pandas as pd,numpy as np
from nexus.core.exceptions import NexusError
def calculate_returns(prices: pd.Series, method: str = "simple") -> pd.Series:
    if method == "simple": return prices.pct_change()
    elif method == "log": return np.log(prices / prices.shift(1))
    else: raise ValueError(f"Unknown method: {method}")
```

### Type Hints
- **Required**: Full type hints on all public APIs
- **Style**: Use `from __future__ import annotations` for forward references
- **Generics**: Use `typing` module for complex types

```python
from __future__ import annotations
from typing import Dict, List, Optional, Union
import pandas as pd

def validate_data(data: pd.DataFrame,
                 required_columns: List[str]) -> Optional[str]:
    """Validate DataFrame has required columns.

    Returns error message if invalid, None if valid.
    """
    missing = [col for col in required_columns if col not in data.columns]
    if missing:
        return f"Missing columns: {missing}"
    return None
```

### Naming Conventions
- **Functions/Methods**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private**: Leading underscore `_private_method`
- **Modules**: `snake_case.py`

```python
# Classes
class DataManager:
    pass

class SimpleRSIStrategy:
    pass

# Functions and methods
def calculate_sharpe_ratio(returns: pd.Series) -> float:
    pass

def _validate_inputs(self, params: Dict) -> bool:
    pass

# Constants
DEFAULT_RISK_FREE_RATE = 0.02
MAX_POSITION_SIZE = 0.1
```

### Error Handling
- **Custom Exceptions**: Inherit from base `NexusError`
- **Descriptive Messages**: Include context and suggestions
- **Logging**: Use appropriate levels (DEBUG, INFO, WARNING, ERROR)

```python
from nexus.core.exceptions import ValidationError
from nexus.core.logging import get_logger

logger = get_logger(__name__)

def validate_strategy_params(params: Dict) -> None:
    """Validate strategy parameters."""
    if "rsi_period" not in params:
        raise ValidationError(
            "Missing 'rsi_period' parameter. "
            "Expected: rsi_period (int, 2-50)"
        )

    period = params["rsi_period"]
    if not isinstance(period, int) or not (2 <= period <= 50):
        raise ValidationError(
            f"Invalid rsi_period: {period}. "
            "Must be integer between 2-50"
        )

    logger.info(f"Validated strategy params: {params}")
```

### Documentation
- **Docstrings**: Google-style for all public functions/classes
- **Comments**: Explain complex logic, not obvious code
- **Examples**: Include usage examples where helpful

```python
def calculate_portfolio_weights(assets: List[str],
                              method: str = "equal_weight") -> Dict[str, float]:
    """Calculate portfolio weights using specified method.

    Args:
        assets: List of asset symbols/tickers
        method: Weighting method ('equal_weight', 'market_cap', etc.)

    Returns:
        Dictionary mapping asset symbols to weights (0.0-1.0)

    Raises:
        ValueError: If method is not supported

    Example:
        >>> assets = ['AAPL', 'MSFT', 'GOOGL']
        >>> weights = calculate_portfolio_weights(assets)
        >>> print(weights)
        {'AAPL': 0.3333, 'MSFT': 0.3333, 'GOOGL': 0.3333}
    """
    if method == "equal_weight":
        weight = 1.0 / len(assets)
        return {asset: weight for asset in assets}
    else:
        raise ValueError(f"Unsupported weighting method: {method}")
```

## 🏗️ Architecture Patterns

### Data Classes
- Use `@dataclass` for simple data containers
- Include type hints and default values
- Add `__post_init__` for validation if needed

```python
from dataclasses import dataclass
from typing import Optional
import pandas as pd

@dataclass
class TradeSignal:
    """Represents a trading signal with metadata."""
    signal: str  # 'BUY', 'SELL', 'HOLD'
    confidence: float  # 0.0 to 1.0
    timestamp: pd.Timestamp
    price: Optional[float] = None
    reasoning: str = ""

    def __post_init__(self):
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("Confidence must be between 0.0 and 1.0")
```

### Abstract Base Classes
- Use `ABC` for strategy interfaces
- Define clear contracts with abstract methods
- Include helper methods where appropriate

```python
from abc import ABC, abstractmethod
from typing import Dict, Any
import pandas as pd

class BaseStrategy(ABC):
    """Abstract base class for all trading strategies."""

    def __init__(self, **params):
        self.params = params
        self._validate_params()

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> List[TradeSignal]:
        """Generate trading signals from market data."""
        pass

    def _validate_params(self) -> None:
        """Validate strategy parameters."""
        pass
```

### Dependency Injection
- Pass dependencies explicitly rather than importing
- Makes testing easier and dependencies clear

```python
# Good - dependencies injected
class BacktestEngine:
    def __init__(self, data_manager: DataManager, risk_manager: RiskManager):
        self.data_manager = data_manager
        self.risk_manager = risk_manager

# Bad - hidden dependencies
class BacktestEngine:
    def __init__(self):
        self.data_manager = DataManager()  # Hidden dependency
        self.risk_manager = RiskManager()  # Hidden dependency
```

## 🧪 Testing Standards

### Unit Tests
- Test one thing at a time
- Use descriptive test names
- Mock external dependencies
- Test both success and failure cases

```python
import pytest
from unittest.mock import Mock
import pandas as pd

class TestDataManager:
    def test_get_ohlcv_data_success(self, mock_api_client):
        """Test successful OHLCV data retrieval."""
        # Arrange
        manager = DataManager(api_client=mock_api_client)
        expected_data = pd.DataFrame({
            'open': [100, 101, 102],
            'high': [105, 106, 107],
            'low': [95, 96, 97],
            'close': [103, 104, 105],
            'volume': [1000, 1100, 1200]
        })

        # Act
        result = manager.get_ohlcv_data('AAPL', '1d', '2023-01-01', '2023-01-03')

        # Assert
        pd.testing.assert_frame_equal(result, expected_data)

    def test_get_ohlcv_data_invalid_symbol(self, mock_api_client):
        """Test error handling for invalid symbol."""
        # Arrange
        manager = DataManager(api_client=mock_api_client)
        mock_api_client.get_ohlcv.side_effect = ValueError("Invalid symbol")

        # Act & Assert
        with pytest.raises(DataError, match="Invalid symbol"):
            manager.get_ohlcv_data('INVALID', '1d', '2023-01-01', '2023-01-03')
```

### Integration Tests
- Test component interactions
- Use realistic data where possible
- Focus on end-to-end workflows

### Test Coverage
- Aim for >90% coverage on critical paths
- Focus on business logic, not trivial getters/setters
- Use coverage reports to identify gaps

## 🔄 Development Workflow

### Git Standards
- **Branching**: `feature/*`, `bugfix/*`, `hotfix/*`
- **Commits**: `type(scope): description` (feat, fix, docs, style, refactor, test, chore)
- **PRs**: Self-review before requesting review, include tests

### Code Review
- **Focus**: Correctness, clarity, test coverage, performance
- **Style**: Use automated tools (black, flake8, mypy) for formatting
- **Discussion**: Comment on architecture decisions, not preferences

### CI/CD Pipeline
- **Lint**: flake8 + mypy on every commit
- **Test**: Full test suite on PR and merge
- **Build**: Documentation build verification
- **Security**: Automated dependency scanning

## 🛠️ Tools & Setup

### Development Environment
```bash
# Install development dependencies
pip install -r requirements.txt

# Set up pre-commit hooks
pre-commit install

# Run full quality check
make check  # lint + test + type check
```

### IDE Configuration
- **VS Code**: Python extension, Black formatter, Flake8 linter
- **PyCharm**: Configure Black as formatter, enable mypy
- **General**: EditorConfig for consistent settings

### Makefile Commands
```makefile
.PHONY: install test lint format check docs clean

install:
	pip install -r requirements.txt

test:
	pytest --cov=nexus --cov-report=html

lint:
	flake8 nexus/ tests/

format:
	black nexus/ tests/

check: lint test
	mypy nexus/ --ignore-missing-imports

docs:
	cd docs && make html

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf .coverage htmlcov docs/_build
```

## 📚 Resources

- [PEP 8](https://pep8.org/) - Python style guide
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [Black Code Style](https://black.readthedocs.io/en/stable/the_black_code_style/current_style.html)
- [MyPy Type Checking](https://mypy.readthedocs.io/)

---

*Style guidelines evolve with the codebase. Propose changes via PR with justification.*
