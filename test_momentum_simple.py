#!/usr/bin/env python3
"""Simple test of momentum strategy implementation."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from nexus.strategies import MomentumStrategy, StrategyFactory
from datetime import datetime

def test_momentum_strategy():
    """Test momentum strategy basic functionality."""
    print("Testing Momentum Strategy Implementation")

    # Test strategy creation
    strategy = MomentumStrategy()
    print(f"✓ Strategy created: {strategy}")

    # Test metadata
    metadata = strategy.metadata
    print(f"✓ Metadata: {metadata.name}, version {metadata.version}")

    # Test parameter validation
    try:
        strategy.validate_parameters()
        print("✓ Parameter validation passed")
    except Exception as e:
        print(f"✗ Parameter validation failed: {e}")
        return False

    # Test strategy registration
    if StrategyFactory.is_registered('momentum'):
        print("✓ Strategy registered with factory")
    else:
        print("✗ Strategy not registered")
        return False

    # Test factory creation
    try:
        created_strategy = StrategyFactory.create('momentum')
        print(f"✓ Factory creation successful: {created_strategy}")
    except Exception as e:
        print(f"✗ Factory creation failed: {e}")
        return False

    print("\n🎉 All basic tests passed!")
    return True

def test_signal_generation():
    """Test signal generation logic."""
    print("\nTesting Signal Generation")

    # Mock market data
    class MockMarketData:
        def __init__(self):
            self.universe = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'NVDA', 'AMZN', 'META', 'NFLX', 'SPY', 'QQQ']
            self.price_data = {
                'AAPL': 150.0, 'GOOGL': 100.0, 'MSFT': 300.0, 'TSLA': 200.0,
                'NVDA': 400.0, 'AMZN': 120.0, 'META': 250.0, 'NFLX': 350.0,
                'SPY': 400.0, 'QQQ': 380.0
            }
            self.volume_data = {sym: 10000 for sym in self.universe}

        def get_universe(self):
            return self.universe

        def get_price(self, symbol):
            return self.price_data.get(symbol, 100.0)

        def get_volume(self, symbol):
            return self.volume_data.get(symbol, 1000)

        def get_historical_data(self, symbol, days):
            # Simple mock: return 6 months of price movements
            base_price = self.price_data.get(symbol, 100.0)
            # Winners: TSLA, AAPL, NVDA, AMZN
            if symbol in ['TSLA', 'AAPL', 'NVDA', 'AMZN']:
                prices = [base_price * (0.9 + i * 0.02) for i in range(days)]
            else:  # Losers: GOOGL, MSFT, META, NFLX, SPY, QQQ
                prices = [base_price * (1.1 - i * 0.015) for i in range(days)]

            return [
                {
                    'date': f'2023-{i+1:02d}-01',
                    'close': price
                }
                for i, price in enumerate(prices)
            ]

    # Create strategy and market data
    strategy = MomentumStrategy(percentile=50.0)  # Test with 50% for 2 winners/losers
    market_data = MockMarketData()

    # Generate signals
    try:
        signals = strategy.generate_signals(market_data)
        print(f"✓ Generated {len(signals)} signals")

        # Check signal structure
        for signal in signals:
            print(f"  - {signal.symbol}: {signal.direction} (confidence: {signal.confidence:.2f})")
            assert signal.symbol in market_data.universe
            assert signal.direction in ['long', 'short']
            assert 0.0 <= signal.confidence <= 1.0
            assert 'position_size' in signal.metadata

        print("✓ Signal structure validation passed")
        return True

    except Exception as e:
        print(f"✗ Signal generation failed: {e}")
        return False

if __name__ == "__main__":
    success1 = test_momentum_strategy()
    success2 = test_signal_generation()

    if success1 and success2:
        print("\n🎯 Momentum Strategy Task 2.4 Implementation: COMPLETE")
        print("Ready for Task 2.5 statistical backtesting validation")
    else:
        print("\n❌ Implementation has issues - fix before proceeding")
        sys.exit(1)
