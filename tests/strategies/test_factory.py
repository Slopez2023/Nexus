"""Tests for StrategyFactory."""

import pytest

from nexus.strategies import (
    StrategyFactory,
    BaseStrategy,
    StrategyMetadata,
    ParameterSpec,
    StrategyError,
)


class TestStrategyFactory:
    """Test StrategyFactory registration and creation."""

    def setup_method(self):
        """Clear registry before each test."""
        StrategyFactory.clear_registry()

    def teardown_method(self):
        """Clear registry after each test."""
        StrategyFactory.clear_registry()

    def test_initial_state(self):
        """Test factory starts empty."""
        assert StrategyFactory.list_strategies() == []
        assert StrategyFactory.get_registry_size() == 0

    def test_register_valid_strategy(self):
        """Test registering a valid strategy."""
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

        StrategyFactory.register(TestStrategy)

        assert "test" in StrategyFactory.list_strategies()
        assert StrategyFactory.is_registered("test") is True
        assert StrategyFactory.get_registry_size() == 1

        info = StrategyFactory.get_strategy_info("test")
        assert info["name"] == "test"
        assert info["class"] == "TestStrategy"

    def test_register_strategy_with_suffix(self):
        """Test registering strategy with 'Strategy' suffix."""
        class RSIStrategy(BaseStrategy):
            def generate_signals(self, market_data):
                return []

            def validate_parameters(self):
                return True

            @property
            def metadata(self):
                return StrategyMetadata(
                    name="RSI Strategy",
                    description="RSI",
                    version="1.0",
                    parameters={},
                    risk_profile={},
                    tags=[]
                )

        StrategyFactory.register(RSIStrategy)
        assert "rsi" in StrategyFactory.list_strategies()

    def test_register_duplicate_strategy(self):
        """Test registering the same strategy twice."""
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

        StrategyFactory.register(TestStrategy)
        # Should be idempotent
        StrategyFactory.register(TestStrategy)

        assert StrategyFactory.list_strategies() == ["test"]
        assert StrategyFactory.get_registry_size() == 1

    def test_register_invalid_strategy(self):
        """Test registering invalid strategies."""
        # Not a class
        with pytest.raises(TypeError):
            StrategyFactory.register("not_a_class")  # type: ignore

        # Doesn't inherit from BaseStrategy
        class NotAStrategy:
            pass

        with pytest.raises(ValueError, match="Must inherit from BaseStrategy"):
            StrategyFactory.register(NotAStrategy)  # type: ignore

    def test_unregister_strategy(self):
        """Test unregistering strategies."""
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

        StrategyFactory.register(TestStrategy)
        assert StrategyFactory.is_registered("test") is True

        StrategyFactory.unregister("test")
        assert StrategyFactory.is_registered("test") is False
        assert StrategyFactory.list_strategies() == []

    def test_unregister_unknown_strategy(self):
        """Test unregistering unknown strategy."""
        with pytest.raises(ValueError, match="Strategy not registered"):
            StrategyFactory.unregister("unknown")

    def test_create_valid_strategy(self):
        """Test creating a valid strategy instance."""
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

        StrategyFactory.register(TestStrategy)
        strategy = StrategyFactory.create("test")

        assert isinstance(strategy, TestStrategy)
        assert isinstance(strategy, BaseStrategy)

    def test_create_strategy_with_parameters(self):
        """Test creating strategy with parameters."""
        class TestStrategy(BaseStrategy):
            def __init__(self, **params):
                super().__init__(**params)
                self.test_param = params.get("test_param", "default")

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

        StrategyFactory.register(TestStrategy)
        strategy = StrategyFactory.create("test", test_param="custom")

        assert isinstance(strategy, TestStrategy)
        assert strategy.test_param == "custom"

    def test_create_unknown_strategy(self):
        """Test creating unknown strategy."""
        with pytest.raises(ValueError, match="Unknown strategy"):
            StrategyFactory.create("unknown")

    def test_create_strategy_with_invalid_params(self):
        """Test creating strategy with invalid parameters."""
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

        StrategyFactory.register(TestStrategy)

        with pytest.raises(StrategyError, match="Strategy creation failed"):
            StrategyFactory.create("test")

    def test_list_strategies_sorted(self):
        """Test that strategies are listed in sorted order."""
        class CStrategy(BaseStrategy):
            def generate_signals(self, market_data): return []
            def validate_parameters(self): return True
            @property
            def metadata(self): return StrategyMetadata("C", "C", "1.0", {}, {}, [])

        class AStrategy(BaseStrategy):
            def generate_signals(self, market_data): return []
            def validate_parameters(self): return True
            @property
            def metadata(self): return StrategyMetadata("A", "A", "1.0", {}, {}, [])

        class BStrategy(BaseStrategy):
            def generate_signals(self, market_data): return []
            def validate_parameters(self): return True
            @property
            def metadata(self): return StrategyMetadata("B", "B", "1.0", {}, {}, [])

        StrategyFactory.register(CStrategy)
        StrategyFactory.register(AStrategy)
        StrategyFactory.register(BStrategy)

        strategies = StrategyFactory.list_strategies()
        assert strategies == ["a", "b", "c"]

    def test_get_strategy_info_unknown(self):
        """Test getting info for unknown strategy."""
        with pytest.raises(ValueError, match="Unknown strategy"):
            StrategyFactory.get_strategy_info("unknown")

    def test_clear_registry(self):
        """Test clearing the registry."""
        class TestStrategy(BaseStrategy):
            def generate_signals(self, market_data): return []
            def validate_parameters(self): return True
            @property
            def metadata(self): return StrategyMetadata("Test", "Test", "1.0", {}, {}, [])

        StrategyFactory.register(TestStrategy)
        assert StrategyFactory.get_registry_size() == 1

        StrategyFactory.clear_registry()
        assert StrategyFactory.get_registry_size() == 0
        assert StrategyFactory.list_strategies() == []
