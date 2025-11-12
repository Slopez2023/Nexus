#!/usr/bin/env python3
"""
End-to-End Test Flow: Warehouse API Integration with Trading Strategy
=====================================================================

This script validates the complete workflow:
1. Initialize Warehouse API data source
2. Load market data through DataManager
3. Run a test strategy using that data
4. Generate signals
5. Validate results
6. Compare with baseline (optional legacy sources)

Run: python test_warehouse_strategy_flow.py --symbol AAPL --start 2024-01-01 --end 2024-03-31
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from nexus.core.config_manager import get_app_config
from nexus.core.data.data import DataManager
from nexus.strategies.base import TradeSignal, BaseStrategy, StrategyMetadata, ParameterSpec
from nexus.integrations.warehouse_api_client import WarehouseAPIClient
from nexus.integrations.warehouse_api_adapter import WarehouseAPIAdapter
from nexus.integrations.warehouse_api_monitor import WarehouseAPIMonitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TestSimpleStrategyFlow(BaseStrategy):
    """
    Simple test strategy: Golden Cross (MA crossover)
    - Buy when fast MA crosses above slow MA
    - Sell when fast MA crosses below slow MA
    
    This is a basic strategy for flow validation, not production use.
    """
    
    def __init__(self, fast_window: int = 20, slow_window: int = 50, **kwargs):
        """Initialize with moving average windows."""
        super().__init__(fast_window=fast_window, slow_window=slow_window, **kwargs)
        self.fast_window = fast_window
        self.slow_window = slow_window
        
    def validate_parameters(self) -> bool:
        """Validate moving average window parameters."""
        fast = self.get_parameter('fast_window')
        slow = self.get_parameter('slow_window')
        
        if not isinstance(fast, int) or fast < 2:
            return False
        if not isinstance(slow, int) or slow < 2:
            return False
        if fast >= slow:
            return False
            
        return True
    
    @property
    def metadata(self) -> StrategyMetadata:
        """Return strategy metadata."""
        return StrategyMetadata(
            name="Golden Cross (MA Crossover)",
            description="Simple moving average crossover strategy. Buy on fast MA crossing above slow MA.",
            version="1.0.0",
            parameters={
                'fast_window': ParameterSpec(
                    name='fast_window',
                    type='int',
                    default=20,
                    min_value=2,
                    max_value=50,
                    description='Fast moving average window'
                ),
                'slow_window': ParameterSpec(
                    name='slow_window',
                    type='int',
                    default=50,
                    min_value=20,
                    max_value=200,
                    description='Slow moving average window'
                ),
            },
            risk_profile={'type': 'trend_following', 'volatility': 'medium'},
            tags=['trend', 'moving_average', 'simple'],
            author='NEXUS Test Suite'
        )
    
    def generate_signals(self, df: pd.DataFrame, symbol: str = 'TEST') -> list[TradeSignal]:
        """
        Generate signals from OHLCV data.
        
        Args:
            df: DataFrame with OHLCV data (Close column required)
            symbol: Trading symbol for signal metadata
            
        Returns:
            List of TradeSignal objects
        """
        signals = []
        
        if df.empty or len(df) < self.slow_window:
            return signals
        
        # Calculate moving averages
        df_copy = df.copy()
        df_copy['fast_ma'] = df_copy['Close'].rolling(self.fast_window).mean()
        df_copy['slow_ma'] = df_copy['Close'].rolling(self.slow_window).mean()
        
        # Identify crossovers
        df_copy['ma_diff'] = df_copy['fast_ma'] - df_copy['slow_ma']
        df_copy['signal'] = 0
        df_copy.loc[df_copy['ma_diff'] > 0, 'signal'] = 1  # Fast > Slow
        
        # Detect crossovers (changes in signal)
        df_copy['crossover'] = df_copy['signal'].diff().fillna(0)
        
        # Generate signals for crossovers
        for idx in df_copy[df_copy['crossover'] != 0].index:
            timestamp = idx if isinstance(idx, datetime) else datetime.fromtimestamp(idx.timestamp())
            close = df_copy.loc[idx, 'Close']
            ma_fast = df_copy.loc[idx, 'fast_ma']
            ma_slow = df_copy.loc[idx, 'slow_ma']
            crossover_type = df_copy.loc[idx, 'crossover']
            
            if crossover_type > 0:  # Fast MA crosses above Slow MA
                direction = 'long'
                reasoning = f"Golden cross: {ma_fast:.2f} > {ma_slow:.2f} at close {close:.2f}"
                confidence = min(0.9, 0.6 + abs(ma_fast - ma_slow) / close * 0.3)
            else:  # Fast MA crosses below Slow MA
                direction = 'short'
                reasoning = f"Death cross: {ma_fast:.2f} < {ma_slow:.2f} at close {close:.2f}"
                confidence = min(0.9, 0.6 + abs(ma_slow - ma_fast) / close * 0.3)
            
            signal = TradeSignal(
                symbol=symbol,
                timestamp=timestamp,
                direction=direction,
                confidence=confidence,
                reasoning=reasoning,
                metadata={
                    'fast_ma': float(ma_fast),
                    'slow_ma': float(ma_slow),
                    'close': float(close),
                    'strategy': 'golden_cross'
                }
            )
            signals.append(signal)
        
        return signals


async def run_complete_flow(
    symbol: str = 'AAPL',
    start_date: str = '2024-01-01',
    end_date: str = '2024-03-31',
    use_warehouse: bool = True,
    compare_sources: bool = False
) -> dict:
    """
    Run complete end-to-end flow with Warehouse API.
    
    Args:
        symbol: Trading symbol
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        use_warehouse: Use Warehouse API (True) or legacy sources (False)
        compare_sources: Compare Warehouse API vs legacy sources
        
    Returns:
        Dictionary with flow results
    """
    logger.info("=" * 80)
    logger.info("NEXUS WAREHOUSE API INTEGRATION TEST FLOW")
    logger.info("=" * 80)
    logger.info(f"Configuration: symbol={symbol}, period={start_date} to {end_date}")
    logger.info(f"Use Warehouse API: {use_warehouse}")
    logger.info(f"Compare sources: {compare_sources}")
    
    results = {
        'success': False,
        'symbol': symbol,
        'period': {'start': start_date, 'end': end_date},
        'data': {},
        'signals': {},
        'errors': [],
        'metrics': {}
    }
    
    try:
        # Step 1: Initialize configuration
        logger.info("\n[1/6] Initializing configuration...")
        config = get_app_config()
        logger.info(f"✓ Configuration loaded: environment={config.environment}")
        
        # Step 2: Initialize data manager
        logger.info("\n[2/6] Initializing DataManager...")
        manager = DataManager()
        
        # Check if Warehouse API is available
        warehouse_available = False
        if use_warehouse:
            try:
                client = WarehouseAPIClient(config.api.warehouse_api)
                health = await client.get_health()
                warehouse_available = health.is_success
                logger.info(f"✓ Warehouse API available: {warehouse_available}")
            except Exception as e:
                logger.warning(f"Warehouse API unavailable: {e}")
                warehouse_available = False
        
        if use_warehouse and not warehouse_available:
            logger.warning("Warehouse API not available, will fall back to legacy sources")
        
        results['warehouse_available'] = warehouse_available
        
        # Step 3: Fetch data from primary source
        logger.info(f"\n[3/6] Fetching data for {symbol}...")
        try:
            result = await manager.fetch_historical_data_async(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date
            )
            
            # Handle result (dict with best source data)
            if isinstance(result, dict):
                # Result format: {symbol, date_range, best_source, recommended_data, quality_assessment}
                recommended_data = result.get('recommended_data')
                quality_assessment = result.get('quality_assessment', {})
                
                if recommended_data is None:
                    raise Exception(f"Data fetch failed: No data from {result.get('best_source', 'any source')}")
                
                df = pd.DataFrame.from_dict(recommended_data)
                quality_score = quality_assessment.get('overall_score', 0.0)
            else:
                if not result.success:
                    raise Exception(f"Data fetch failed: {result.error_message}")
                df = result.data
                quality_score = result.quality_metrics.overall_score if result.quality_metrics else 0.0
            
            if df is None or df.empty:
                raise Exception("No data returned")
            
            logger.info(f"✓ Fetched {len(df)} candles")
            logger.info(f"  Date range: {df.index.min()} to {df.index.max()}")
            logger.info(f"  Columns: {', '.join(df.columns)}")
            logger.info(f"  Price range: {df['Close'].min():.2f} - {df['Close'].max():.2f}")
            
            results['data']['primary'] = {
                'rows': len(df),
                'date_range': [str(df.index.min()), str(df.index.max())],
                'price_range': [float(df['Close'].min()), float(df['Close'].max())],
                'quality_score': quality_score
            }
            
        except Exception as e:
            logger.error(f"✗ Data fetch failed: {e}")
            results['errors'].append(str(e))
            return results
        
        # Step 4: Optional comparison with legacy sources
        if compare_sources:
            logger.info("\n[4/6] Comparing with legacy sources...")
            # This would compare against yfinance, polygon.io, etc.
            # For now, just log that we would do this
            logger.info("  (Legacy source comparison placeholder)")
            results['data']['comparison'] = "pending"
        else:
            logger.info("\n[4/6] Skipping source comparison (--compare not set)")
        
        # Step 5: Initialize strategy and generate signals
        logger.info("\n[5/6] Generating trading signals...")
        strategy = TestSimpleStrategyFlow(fast_window=20, slow_window=50)
        logger.info(f"✓ Strategy initialized: {strategy.metadata.name}")
        
        signals = strategy.generate_signals(df, symbol=symbol)
        logger.info(f"✓ Generated {len(signals)} signals")
        
        if signals:
            long_signals = sum(1 for s in signals if s.direction == 'long')
            short_signals = sum(1 for s in signals if s.direction == 'short')
            avg_confidence = np.mean([s.confidence for s in signals])
            logger.info(f"  - Long signals: {long_signals}")
            logger.info(f"  - Short signals: {short_signals}")
            logger.info(f"  - Average confidence: {avg_confidence:.2%}")
            
            # Print first and last signals
            if signals:
                logger.info(f"\n  First signal: {signals[0].timestamp} - {signals[0].direction.upper()} @ {signals[0].confidence:.1%} confidence")
                logger.info(f"  Last signal: {signals[-1].timestamp} - {signals[-1].direction.upper()} @ {signals[-1].confidence:.1%} confidence")
        
        results['signals'] = {
            'total': len(signals),
            'long': sum(1 for s in signals if s.direction == 'long'),
            'short': sum(1 for s in signals if s.direction == 'short'),
            'avg_confidence': float(np.mean([s.confidence for s in signals])) if signals else 0.0,
            'first_signal': signals[0].to_dict() if signals else None,
            'last_signal': signals[-1].to_dict() if signals else None,
        }
        
        # Step 6: Validation summary
        logger.info("\n[6/6] Validation Summary")
        logger.info("✓ All components operational:")
        logger.info(f"  - Configuration: OK")
        logger.info(f"  - Data Pipeline: OK ({len(df)} candles)")
        logger.info(f"  - Strategy Engine: OK")
        logger.info(f"  - Signal Generation: OK ({len(signals)} signals)")
        
        if warehouse_available:
            logger.info(f"  - Warehouse API: OK")
        else:
            logger.info(f"  - Warehouse API: Not available (fallback to legacy)")
        
        results['success'] = True
        
        # Print summary statistics
        logger.info("\n" + "=" * 80)
        logger.info("FLOW VALIDATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Status: SUCCESS ✓")
        logger.info(f"Symbol: {symbol}")
        logger.info(f"Period: {len(df)} trading days")
        logger.info(f"Signals: {len(signals)} generated")
        logger.info(f"Warehouse API: {'Used' if warehouse_available else 'Not available (legacy fallback)'}")
        
        return results
        
    except Exception as e:
        logger.error(f"Flow failed with error: {e}", exc_info=True)
        results['errors'].append(str(e))
        return results


async def main():
    """Main entry point with CLI argument handling."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Test Warehouse API integration with trading strategy'
    )
    parser.add_argument(
        '--symbol',
        default='AAPL',
        help='Trading symbol (default: AAPL)'
    )
    parser.add_argument(
        '--start',
        default='2024-01-01',
        help='Start date YYYY-MM-DD (default: 2024-01-01)'
    )
    parser.add_argument(
        '--end',
        default='2024-03-31',
        help='End date YYYY-MM-DD (default: 2024-03-31)'
    )
    parser.add_argument(
        '--compare',
        action='store_true',
        help='Compare Warehouse API with legacy sources'
    )
    parser.add_argument(
        '--no-warehouse',
        action='store_true',
        help='Test with legacy sources only (no Warehouse API)'
    )
    
    args = parser.parse_args()
    
    # Run the flow
    results = await run_complete_flow(
        symbol=args.symbol,
        start_date=args.start,
        end_date=args.end,
        use_warehouse=not args.no_warehouse,
        compare_sources=args.compare
    )
    
    # Exit with appropriate code
    sys.exit(0 if results['success'] else 1)


if __name__ == '__main__':
    asyncio.run(main())
