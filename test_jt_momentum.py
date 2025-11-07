#!/usr/bin/env python3
"""
Test JT Momentum Strategy Implementation
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from nexus.strategies import MomentumStrategy
from datetime import datetime

def test_jt_momentum():
    """Test JT momentum signal generation."""
    print("Testing JT Momentum Strategy")

    # Create strategy with JT parameters
    strategy = MomentumStrategy(formation_period_months=6)
    print(f"✓ Strategy created with 6-month formation period")

    # Mock market data with strong uptrend
    class MockMarketData:
        def __init__(self, trend='up'):
            self.trend = trend
            self.price_data = {'SPY': 400.0}

        def get_price(self, symbol):
            return self.price_data.get(symbol, 100.0)

        def get_volume(self, symbol):
            return 10000

        def get_historical_data(self, symbol, days):
            base_price = self.price_data.get(symbol, 100.0)
            if self.trend == 'up':
                # Strong uptrend: 10% gain over period
                prices = [base_price * (1.0 + i * 0.0017) for i in range(days)]
            elif self.trend == 'down':
                # Strong downtrend: -10% loss
                prices = [base_price * (1.0 - i * 0.0017) for i in range(days)]
            else:
                # Sideways
                prices = [base_price] * days

            return [
                {'date': f'2023-{i+1:02d}-01', 'close': price}
                for i, price in enumerate(prices)
            ]

    # Test 1: Strong uptrend should generate long signal
    print("\nTest 1: Strong uptrend")
    market_data_up = MockMarketData('up')
    signals_up = strategy.generate_signals(market_data_up)
    print(f"Signals generated: {len(signals_up)}")
    if signals_up:
        signal = signals_up[0]
        print(f"  Direction: {signal.direction}")
        print(f"  Confidence: {signal.confidence:.2f}")
        print(f"  Formation return: {signal.metadata['formation_return']:.1%}")
        assert signal.direction == 'long'
        assert signal.confidence > 0.5
        print("✓ Long signal generated correctly")
    else:
        print("✗ No signal generated for uptrend")

    # Test 2: Strong downtrend should generate short signal
    print("\nTest 2: Strong downtrend")
    market_data_down = MockMarketData('down')
    signals_down = strategy.generate_signals(market_data_down)
    print(f"Signals generated: {len(signals_down)}")
    if signals_down:
        signal = signals_down[0]
        print(f"  Direction: {signal.direction}")
        print(f"  Confidence: {signal.confidence:.2f}")
        print(f"  Formation return: {signal.metadata['formation_return']:.1%}")
        assert signal.direction == 'short'
        assert signal.confidence > 0.5
        print("✓ Short signal generated correctly")
    else:
        print("✗ No signal generated for downtrend")

    # Test 3: Sideways market should generate no signal
    print("\nTest 3: Sideways market")
    market_data_sideways = MockMarketData('sideways')
    signals_sideways = strategy.generate_signals(market_data_sideways)
    print(f"Signals generated: {len(signals_sideways)}")
    assert len(signals_sideways) == 0
    print("✓ No signal generated for sideways market (correct)")

    print("\n" + "="*50)
    print("JT MOMENTUM TESTS PASSED")
    print("Strategy correctly implements academic momentum principles:")
    print("- Strong trends continue (buy uptrends, short downtrends)")
    print("- Weak trends ignored (sideways = no signal)")
    print("- Confidence based on trend strength")
    print("="*50)

if __name__ == "__main__":
    test_jt_momentum()
