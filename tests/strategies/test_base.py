"""Tests for base strategy components."""

import pytest
from datetime import datetime
from unittest.mock import Mock

from nexus.strategies import (
    TradeSignal,
    BaseStrategy,
    StrategyMetadata,
    ParameterSpec,
    MarketData,
    ParameterError,
    SignalError,
    ValidationError,
)


class TestTradeSignal:
    """Test TradeSignal creation, validation, and operations."""

    def test_valid_signal_creation(self):
        """Test creating a valid signal."""
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
        assert signal.reasoning == "RSI oversold"
        assert signal.metadata == {"rsi": 25.5}

    def test_invalid_symbol(self):
        """Test validation of invalid symbols."""
        with pytest.raises(ValueError, match="Invalid symbol"):
            TradeSignal(
                symbol="",
                timestamp=datetime.now(),
                direction="long",
                confidence=0.8,
                reasoning="Test",
                metadata={}
            )

        with pytest.raises(ValueError, match="Invalid symbol"):
            TradeSignal(
                symbol=None,  # type: ignore
                timestamp=datetime.now(),
                direction="long",
                confidence=0.8,
                reasoning="Test",
                metadata={}
            )

    def test_invalid_direction(self):
        """Test validation of invalid directions."""
        with pytest.raises(ValueError, match="Invalid direction"):
            TradeSignal(
                symbol="AAPL",
                timestamp=datetime.now(),
                direction="buy",  # Invalid
                confidence=0.8,
                reasoning="Test",
                metadata={}
            )

    def test_invalid_confidence(self):
        """Test validation of confidence values."""
        # Too low
        with pytest.raises(ValueError, match="Confidence must be 0.0-1.0"):
            TradeSignal(
                symbol="AAPL",
                timestamp=datetime.now(),
                direction="long",
                confidence=-0.1,
                reasoning="Test",
                metadata={}
            )

        # Too high
        with pytest.raises(ValueError, match="Confidence must be 0.0-1.0"):
            TradeSignal(
                symbol="AAPL",
                timestamp=datetime.now(),
                direction="long",
                confidence=1.5,
                reasoning="Test",
                metadata={}
            )

        # Non-numeric
        with pytest.raises(ValueError, match="Confidence must be 0.0-1.0"):
            TradeSignal(
                symbol="AAPL",
                timestamp=datetime.now(),
                direction="long",
                confidence="high",  # type: ignore
                reasoning="Test",
                metadata={}
            )

    def test_invalid_reasoning(self):
        """Test validation of reasoning."""
        with pytest.raises(ValueError, match="Reasoning required"):
            TradeSignal(
                symbol="AAPL",
                timestamp=datetime.now(),
                direction="long",
                confidence=0.8,
                reasoning="",
                metadata={}
            )

        with pytest.raises(ValueError, match="Reasoning required"):
            TradeSignal(
                symbol="AAPL",
                timestamp=datetime.now(),
                direction="long",
                confidence=0.8,
                reasoning=None,  # type: ignore
                metadata={}
            )

    def test_invalid_metadata(self):
        """Test validation of metadata."""
        with pytest.raises(ValueError, match="Metadata must be dict"):
            TradeSignal(
                symbol="AAPL",
                timestamp=datetime.now(),
                direction="long",
                confidence=0.8,
                reasoning="Test",
                metadata="not_dict"  # type: ignore
            )

    def test_invalid_timestamp(self):
        """Test validation of timestamp."""
        with pytest.raises(ValueError, match="Invalid timestamp"):
            TradeSignal(
                symbol="AAPL",
                timestamp="not_datetime",  # type: ignore
                direction="long",
                confidence=0.8,
                reasoning="Test",
                metadata={}
            )

    def test_immutability(self):
        """Test that signals are immutable."""
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

        with pytest.raises(AttributeError):
            signal.symbol = "GOOGL"  # Should fail - frozen

    def test_confidence_properties(self):
        """Test confidence level properties."""
        high_conf = TradeSignal(
            symbol="AAPL",
            timestamp=datetime.now(),
            direction="long",
            confidence=0.9,
            reasoning="Strong signal",
            metadata={}
        )
        assert high_conf.is_high_confidence is True
        assert high_conf.is_low_confidence is False

        low_conf = TradeSignal(
            symbol="AAPL",
            timestamp=datetime.now(),
            direction="short",
            confidence=0.1,
            reasoning="Weak signal",
            metadata={}
        )
        assert low_conf.is_high_confidence is False
        assert low_conf.is_low_confidence is True

        medium_conf = TradeSignal(
            symbol="AAPL",
            timestamp=datetime.now(),
            direction="long",
            confidence=0.5,
            reasoning="Medium signal",
            metadata={}
        )
        assert medium_conf.is_high_confidence is False
        assert medium_conf.is_low_confidence is False

    def test_serialization(self):
        """Test signal serialization/deserialization."""
        original = TradeSignal(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 1, 12, 30, 45),
            direction="long",
            confidence=0.85,
            reasoning="RSI oversold",
            metadata={"rsi": 25.5, "period": 14}
        )

        data = original.to_dict()
        restored = TradeSignal.from_dict(data)

        assert restored == original
        assert restored.symbol == original.symbol
        assert restored.timestamp == original.timestamp
        assert restored.direction == original.direction
        assert restored.confidence == original.confidence
        assert restored.reasoning == original.reasoning
        assert restored.metadata == original.metadata

    def test_serialization_invalid_data(self):
        """Test serialization with invalid data."""
        # Missing field
        with pytest.raises(ValueError, match="Missing required field"):
            TradeSignal.from_dict({
                "timestamp": "2024-01-01T12:00:00",
                "direction": "long",
                "confidence": 0.8,
                "reasoning": "Test",
                "metadata": {}
                # Missing symbol
            })

        # Invalid timestamp
        with pytest.raises(ValueError, match="Invalid data format"):
            TradeSignal.from_dict({
                "symbol": "AAPL",
                "timestamp": "invalid-date",
                "direction": "long",
                "confidence": 0.8,
                "reasoning": "Test",
                "metadata": {}
            })


class TestParameterSpec:
    """Test ParameterSpec validation."""

    def test_valid_spec_creation(self):
        """Test creating valid parameter specs."""
        spec = ParameterSpec(
            name="period",
            type="int",
            default=14,
            min_value=1,
            max_value=100,
            description="RSI period"
        )
        assert spec.name == "period"
        assert spec.type == "int"
        assert spec.default == 14
        assert spec.min_value == 1
        assert spec.max_value == 100

    def test_invalid_spec(self):
        """Test invalid parameter spec creation."""
        with pytest.raises(ValueError, match="Invalid parameter name"):
            ParameterSpec(name="", type="int", default=1)

        with pytest.raises(ValueError, match="Invalid type"):
            ParameterSpec(name="test", type="invalid", default=1)  # type: ignore

        with pytest.raises(ValueError, match="min_value must be < max_value"):
            ParameterSpec(name="test", type="int", default=1, min_value=10, max_value=5)

    def test_validate_int(self):
        """Test int parameter validation."""
        spec = ParameterSpec(
            name="period",
            type="int",
            default=14,
            min_value=1,
            max_value=100
        )

        assert spec.validate(14) is True
        assert spec.validate(1) is True
        assert spec.validate(100) is True
        assert spec.validate(0) is False  # Below min
        assert spec.validate(101) is False  # Above max
        assert spec.validate("14") is False  # Wrong type
        assert spec.validate(14.0) is False  # Wrong type

    def test_validate_float(self):
        """Test float parameter validation."""
        spec = ParameterSpec(
            name="threshold",
            type="float",
            default=0.5,
            min_value=0.0,
            max_value=1.0
        )

        assert spec.validate(0.5) is True
        assert spec.validate(0.0) is True
        assert spec.validate(1.0) is True
        assert spec.validate(1.5) is False  # Above max
        assert spec.validate(-0.1) is False  # Below min
        assert spec.validate("0.5") is False  # Wrong type

    def test_validate_str(self):
        """Test string parameter validation."""
        spec = ParameterSpec(
            name="method",
            type="str",
            default="sma",
            choices=["sma", "ema", "wma"]
        )

        assert spec.validate("sma") is True
        assert spec.validate("ema") is True
        assert spec.validate("invalid") is False  # Not in choices
        assert spec.validate(123) is False  # Wrong type

    def test_validate_bool(self):
        """Test bool parameter validation."""
        spec = ParameterSpec(name="enabled", type="bool", default=True)

        assert spec.validate(True) is True
        assert spec.validate(False) is True
        assert spec.validate("true") is False  # Wrong type
        assert spec.validate(1) is False  # Wrong type


class TestStrategyMetadata:
    """Test StrategyMetadata creation and validation."""

    def test_valid_metadata_creation(self):
        """Test creating valid strategy metadata."""
        params = {
            "period": ParameterSpec(name="period", type="int", default=14, min_value=1, max_value=100),
            "threshold": ParameterSpec(name="threshold", type="float", default=0.7, min_value=0.0, max_value=1.0)
        }

        metadata = StrategyMetadata(
            name="RSI Strategy",
            description="Relative Strength Index strategy",
            version="1.0.0",
            parameters=params,
            risk_profile={"max_drawdown": 0.1, "sharpe_target": 1.5},
            tags=["momentum", "oscillator"],
            author="NEXUS Team",
            created_date=datetime(2024, 1, 1)
        )

        assert metadata.name == "RSI Strategy"
        assert metadata.version == "1.0.0"
        assert len(metadata.parameters) == 2
        assert "period" in metadata.parameters
        assert metadata.risk_profile["max_drawdown"] == 0.1

    def test_invalid_metadata(self):
        """Test invalid metadata creation."""
        with pytest.raises(ValueError, match="Invalid name"):
            StrategyMetadata(
                name="",
                description="Test",
                version="1.0",
                parameters={},
                risk_profile={},
                tags=[]
            )

        with pytest.raises(ValueError, match="Parameters must be dict"):
            StrategyMetadata(
                name="Test",
                description="Test",
                version="1.0",
                parameters="not_dict",  # type: ignore
                risk_profile={},
                tags=[]
            )

    def test_validate_parameters(self):
        """Test parameter validation."""
        params = {
            "period": ParameterSpec(name="period", type="int", default=14, min_value=1, max_value=100),
            "threshold": ParameterSpec(name="threshold", type="float", default=0.7, min_value=0.0, max_value=1.0)
        }

        metadata = StrategyMetadata(
            name="Test Strategy",
            description="Test",
            version="1.0",
            parameters=params,
            risk_profile={},
            tags=[]
        )

        # Valid parameters
        errors = metadata.validate_parameters({"period": 20, "threshold": 0.8})
        assert errors == []

        # Missing parameter
        errors = metadata.validate_parameters({"period": 20})
        assert len(errors) == 1
        assert "Missing required parameter: threshold" in errors[0]

        # Invalid parameter
        errors = metadata.validate_parameters({"period": 200, "threshold": 0.8})  # period too high
        assert len(errors) == 1
        assert "Invalid value for period" in errors[0]

        # Extra parameter
        errors = metadata.validate_parameters({"period": 20, "threshold": 0.8, "extra": 1})
        assert len(errors) == 1
        assert "Unexpected parameters" in errors[0]


class TestBaseStrategy:
    """Test BaseStrategy abstract interface."""

    def test_abstract_methods(self):
        """Test that BaseStrategy cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseStrategy()  # Should fail - abstract

    def test_parameter_management(self):
        """Test parameter get/set operations."""
        # Create a concrete implementation for testing
        class TestStrategy(BaseStrategy):
            def generate_signals(self, market_data):
                return []

            def validate_parameters(self):
                period = self.get_parameter("period", 14)
                return isinstance(period, int) and 1 <= period <= 100

            @property
            def metadata(self):
                return StrategyMetadata(
                    name="Test Strategy",
                    description="Test",
                    version="1.0",
                    parameters={},
                    risk_profile={},
                    tags=[]
                )

        # Valid initialization
        strategy = TestStrategy(period=20)
        assert strategy.get_parameter("period") == 20
        assert strategy.get_parameter("missing", "default") == "default"

        # Valid parameter update
        strategy.set_parameter("period", 30)
        assert strategy.get_parameter("period") == 30

        # Invalid parameter update
        with pytest.raises(ParameterError):
            strategy.set_parameter("period", 200)  # Too high

        # Parameter should be rolled back
        assert strategy.get_parameter("period") == 30

    def test_invalid_initialization(self):
        """Test initialization with invalid parameters."""
        class TestStrategy(BaseStrategy):
            def generate_signals(self, market_data):
                return []

            def validate_parameters(self):
                return False  # Always invalid

            @property
            def metadata(self):
                return StrategyMetadata(
                    name="Test Strategy",
                    description="Test",
                    version="1.0",
                    parameters={},
                    risk_profile={},
                    tags=[]
                )

        with pytest.raises(ParameterError):
            TestStrategy()

    def test_repr(self):
        """Test string representation."""
        class TestStrategy(BaseStrategy):
            def generate_signals(self, market_data):
                return []

            def validate_parameters(self):
                return True

            @property
            def metadata(self):
                return StrategyMetadata(
                    name="Test Strategy",
                    description="Test",
                    version="1.0",
                    parameters={},
                    risk_profile={},
                    tags=[]
                )

        strategy = TestStrategy(param1="value1", param2=42)
        repr_str = repr(strategy)
        assert "TestStrategy" in repr_str
        assert "param1" in repr_str
        assert "param2" in repr_str
