"""Backtesting engine core implementation.

The main backtesting orchestrator that coordinates strategy execution,
portfolio simulation, cost calculations, and result analysis.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
import time

import pandas as pd

from ..strategies import BaseStrategy, TradeSignal
from .models import (
    BacktestConfig, BacktestResult, PortfolioState, Trade,
    PerformanceMetrics, SignificanceTest
)
from .simulator import PortfolioSimulator
from .costs import TransactionCostModel
from .analyzer import PerformanceAnalyzer
from ..core.data.data import DataManager

logger = logging.getLogger(__name__)


class MarketDataAdapter:
    """Adapter to provide market data interface to strategies.

    Wraps pandas DataFrame to provide the MarketData protocol.
    """

    def __init__(self, data: pd.DataFrame, current_date: datetime):
        """Initialize with market data.

        Args:
            data: DataFrame with OHLCV data indexed by date
            current_date: Current simulation date
        """
        self.data = data
        self.current_date = current_date

    def get_price(self, symbol: str) -> float:
        """Get current price for symbol."""
        try:
            # Get close price for current date
            prices = self.data.xs(symbol, level='symbol', drop_level=False) if 'symbol' in self.data.index.names else self.data
            current_data = prices.loc[self.current_date]
            return float(current_data['close'])
        except (KeyError, IndexError):
            # Fallback to last available price
            symbol_data = self.data.xs(symbol, level='symbol') if 'symbol' in self.data.index.names else self.data
            return float(symbol_data['close'].iloc[-1])

    def get_volume(self, symbol: str) -> int:
        """Get current volume for symbol."""
        try:
            symbol_data = self.data.xs(symbol, level='symbol') if 'symbol' in self.data.index.names else self.data
            current_data = symbol_data.loc[self.current_date]
            return int(current_data['volume'])
        except (KeyError, IndexError):
            return 1000000  # Default volume

    def get_spread(self, symbol: str) -> float:
        """Get current bid-ask spread for symbol.
        
        Estimates spread from high-low range.
        """
        try:
            symbol_data = self.data.xs(symbol, level='symbol') if 'symbol' in self.data.index.names else self.data
            current_data = symbol_data.loc[self.current_date]
            # Estimate spread as ~0.1% of price or based on high-low range
            high = float(current_data['high'])
            low = float(current_data['low'])
            price = float(current_data['close'])
            spread = (high - low) / 2 if (high - low) > 0 else price * 0.001
            return spread
        except (KeyError, IndexError):
            return 0.0

    def get_historical_data(self, symbol: str, days: int) -> List[Dict[str, Any]]:
        """Get historical data for symbol."""
        try:
            symbol_data = self.data.xs(symbol, level='symbol') if 'symbol' in self.data.index.names else self.data

            # Get data up to current date
            historical = symbol_data.loc[:self.current_date].tail(days)

            return [
                {
                    'date': date,
                    'open': row['open'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                    'volume': row['volume']
                }
                for date, row in historical.iterrows()
            ]
        except Exception:
            return []


class BacktestEngine:
    """Professional backtesting engine with statistical rigor.

    Orchestrates the complete backtesting process:
    1. Data validation and preparation
    2. Strategy execution with realistic costs
    3. Portfolio simulation and risk management
    4. Performance analysis and statistical validation
    5. Comprehensive result reporting
    """

    def __init__(self, config: BacktestConfig):
        """Initialize backtesting engine.

        Args:
            config: Backtest configuration
        """
        self.config = config

        # Initialize components
        self.portfolio_simulator = PortfolioSimulator(config)
        self.cost_model = TransactionCostModel(config.transaction_costs)
        self.performance_analyzer = PerformanceAnalyzer()
        self.data_manager = DataManager()

        # Execution tracking
        self.execution_start_time = None
        self.warnings = []
        self.data_source = None  # Track which data source was used

        logger.info(f"Initialized backtest engine: {config.start_date} to {config.end_date}")

    def run_backtest(self, strategy: BaseStrategy, market_data: Optional[pd.DataFrame] = None,
                     symbol: Optional[str] = None, timeframe: Optional[str] = None) -> BacktestResult:
        """Run complete backtest.

        Args:
            strategy: Trading strategy to test
            market_data: Historical market data (OHLCV). If None, loads from {symbol}-*.csv
            symbol: Asset symbol (e.g., 'BTC', 'ETH') - required if market_data is None
            timeframe: Timeframe hint (e.g., '1d', '4h') - used for data lookup

        Returns:
            BacktestResult: Complete backtest results
        """
        self.execution_start_time = time.time()
        logger.info(f"Starting backtest for strategy: {strategy.__class__.__name__}")

        try:
            # Load data if not provided
            if market_data is None:
                market_data = self._load_market_data(symbol, timeframe)

            # Validate inputs
            self._validate_inputs(strategy, market_data)

            # Prepare data
            processed_data = self._prepare_market_data(market_data)

            # Run simulation
            portfolio_states, trades = self._run_simulation(strategy, processed_data)

            # Analyze performance
            performance = self._analyze_performance(portfolio_states, trades)

            # Statistical validation
            significance_tests = self._run_significance_tests(performance, portfolio_states)

            # Create result
            result = BacktestResult(
                config=self.config,
                portfolio_states=portfolio_states,
                trades=trades,
                performance=performance,
                significance_tests=significance_tests,
                equity_curve=self._calculate_equity_curve(portfolio_states),
                drawdowns=self._calculate_drawdowns(portfolio_states),
                monthly_returns=self._calculate_monthly_returns(portfolio_states),
                risk_metrics=self._calculate_risk_metrics(portfolio_states, trades),
                execution_time=time.time() - self.execution_start_time,
                data_quality_score=self._assess_data_quality(market_data),
                warnings=self.warnings
            )

            logger.info(f"Backtest completed: {len(trades)} trades, "
                       f"return={performance.total_return:.2%}, "
                       f"sharpe={performance.sharpe_ratio:.2f}")

            return result

        except Exception as e:
            logger.error(f"Backtest failed: {e}")
            raise

    def _load_market_data(self, symbol: Optional[str], timeframe: Optional[str]) -> pd.DataFrame:
        """Load market data using DataManager (tries local CSVs first).
        
        Args:
            symbol: Asset symbol (required)
            timeframe: Timeframe hint (optional, for logging)
            
        Returns:
            DataFrame with OHLCV data indexed by date
        """
        if not symbol:
            raise ValueError("symbol is required when market_data is not provided")
        
        logger.info(f"Loading data for {symbol} {timeframe or 'any timeframe'} via DataManager")
        
        try:
            # Use DataManager to fetch (LocalOHLCVDataSource will be tried first)
            df = self.data_manager.fetch_historical_data(
                symbol=symbol,
                start_date=self.config.start_date.strftime("%Y-%m-%d"),
                end_date=self.config.end_date.strftime("%Y-%m-%d")
            )
            
            if df.empty:
                raise ValueError(f"No data found for {symbol}")
            
            # Normalize column names to lowercase for consistency
            df.columns = [col.lower() for col in df.columns]
            
            # Track data source
            self.data_source = symbol
            
            logger.info(f"Loaded {len(df)} rows for {symbol}: {df.index.min()} to {df.index.max()}")
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to load data for {symbol}: {e}")
            raise ValueError(f"Data loading failed for {symbol}: {e}")

    def _validate_inputs(self, strategy: BaseStrategy, market_data: pd.DataFrame) -> None:
        """Validate strategy and market data inputs."""
        # Validate strategy
        if not isinstance(strategy, BaseStrategy):
            raise ValueError(f"Strategy must inherit from BaseStrategy: {type(strategy)}")

        # Validate market data
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in market_data.columns for col in required_columns):
            raise ValueError(f"Market data missing required columns: {required_columns}")

        # Check date range
        if market_data.index.min() > self.config.start_date:
            self.warnings.append(f"Data starts after backtest start: {market_data.index.min()}")

        if market_data.index.max() < self.config.end_date:
            self.warnings.append(f"Data ends before backtest end: {market_data.index.max()}")

        # Check data quality
        if market_data.isnull().sum().sum() > 0:
            self.warnings.append("Market data contains missing values")

    def _prepare_market_data(self, market_data: pd.DataFrame) -> pd.DataFrame:
        """Prepare and clean market data for backtesting."""
        # Forward fill missing data (simple approach)
        cleaned_data = market_data.fillna(method='ffill')

        # Filter date range
        date_mask = (cleaned_data.index >= self.config.start_date) & \
                   (cleaned_data.index <= self.config.end_date)
        filtered_data = cleaned_data[date_mask]

        if len(filtered_data) == 0:
            raise ValueError("No market data in specified date range")

        logger.info(f"Prepared {len(filtered_data)} days of market data")
        return filtered_data

    def _run_simulation(self, strategy: BaseStrategy, market_data: pd.DataFrame) -> tuple[List[PortfolioState], List[Trade]]:
        """Run the core simulation loop.

        Args:
            strategy: Trading strategy
            market_data: Prepared market data

        Returns:
            Tuple of (portfolio_states, trades)
        """
        logger.info("Starting simulation loop")

        # Reset portfolio
        self.portfolio_simulator.reset()

        trades = []

        # Simulation loop - daily frequency
        for current_date in market_data.index:
            # Update market prices
            daily_prices = {}
            if 'symbol' in market_data.index.names:
                # Multi-symbol data
                for symbol in market_data.index.get_level_values('symbol').unique():
                    symbol_data = market_data.xs(symbol, level='symbol')
                    if current_date in symbol_data.index:
                        daily_prices[symbol] = symbol_data.loc[current_date, 'close']
            else:
                # Single symbol data
                daily_prices = {'default': market_data.loc[current_date, 'close']}

            self.portfolio_simulator.update_market_prices(daily_prices, current_date)

            # Create market data adapter for strategy
            market_adapter = MarketDataAdapter(market_data, current_date)

            # Generate signals
            signals = strategy.generate_signals(market_adapter)

            # Execute signals
            for signal in signals:
                # Simple execution: market order at close price
                execution_price = daily_prices.get(signal.symbol, signal.metadata.get('price', 100.0))

                # Convert signal to trade quantity
                quantity = signal.confidence * 1000  # Simple position sizing
                if signal.direction == 'short':
                    quantity = -quantity

                # Execute trade
                trade = self.portfolio_simulator.execute_trade(
                    signal.symbol, int(quantity), execution_price,
                    current_date, self.cost_model, market_adapter
                )

                if trade:
                    trades.append(trade)

            # Check risk limits
            if self.portfolio_simulator.is_risk_limits_breached():
                logger.warning(f"Risk limits breached on {current_date}")
                self.warnings.append(f"Risk limits breached on {current_date}")

        portfolio_states = self.portfolio_simulator.get_portfolio_history()

        logger.info(f"Simulation completed: {len(portfolio_states)} portfolio states, {len(trades)} trades")

        return portfolio_states, trades

    def _analyze_performance(self, portfolio_states: List[PortfolioState],
                           trades: List[Trade]) -> PerformanceMetrics:
        """Analyze portfolio performance."""
        return self.performance_analyzer.calculate_metrics(portfolio_states, trades)

    def _run_significance_tests(self, performance: PerformanceMetrics,
                              portfolio_states: List[PortfolioState]) -> List[SignificanceTest]:
        """Run statistical significance tests."""
        # Simplified - would need full implementation
        return []

    def _calculate_equity_curve(self, portfolio_states: List[PortfolioState]) -> pd.Series:
        """Calculate equity curve."""
        values = [state.total_value for state in portfolio_states]
        dates = [state.timestamp for state in portfolio_states]
        return pd.Series(values, index=dates)

    def _calculate_drawdowns(self, portfolio_states: List[PortfolioState]) -> pd.Series:
        """Calculate drawdown series."""
        equity = self._calculate_equity_curve(portfolio_states)
        rolling_max = equity.expanding().max()
        drawdowns = (equity - rolling_max) / rolling_max
        return drawdowns

    def _calculate_monthly_returns(self, portfolio_states: List[PortfolioState]) -> pd.Series:
        """Calculate monthly returns."""
        equity = self._calculate_equity_curve(portfolio_states)
        monthly = equity.resample('M').last().pct_change()
        return monthly.dropna()

    def _calculate_risk_metrics(self, portfolio_states: List[PortfolioState],
                              trades: List[Trade]) -> Dict[str, float]:
        """Calculate additional risk metrics."""
        equity = self._calculate_equity_curve(portfolio_states)

        # Value at Risk (simplified)
        returns = equity.pct_change().dropna()
        var_95 = returns.quantile(0.05)

        # Maximum drawdown
        drawdowns = self._calculate_drawdowns(portfolio_states)
        max_dd = abs(drawdowns.min())

        return {
            'value_at_risk_95': var_95,
            'max_drawdown': max_dd,
            'total_trades': len(trades),
            'winning_trades': sum(1 for t in trades if t.net_amount > 0),
            'avg_trade_pnl': sum(t.net_amount for t in trades) / len(trades) if trades else 0
        }

    def _assess_data_quality(self, market_data: pd.DataFrame) -> float:
        """Assess market data quality (0-1 scale)."""
        score = 1.0

        # Missing data penalty
        missing_pct = market_data.isnull().sum().sum() / (len(market_data) * len(market_data.columns))
        score -= missing_pct * 0.5

        # Date gaps penalty
        date_gaps = pd.date_range(market_data.index.min(), market_data.index.max(), freq='D')
        gap_pct = 1 - (len(market_data) / len(date_gaps))
        score -= gap_pct * 0.3

        return max(0.0, min(1.0, score))
