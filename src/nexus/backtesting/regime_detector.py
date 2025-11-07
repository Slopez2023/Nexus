"""Market regime detection for backtesting.

Implements regime classification to test strategy performance across
different market conditions (bull, bear, sideways, high volatility).
"""

from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
import logging

import pandas as pd
import numpy as np
from sklearn.cluster import KMeans

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Market regime classifications."""
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    HIGH_VOLATILITY = "high_volatility"


@dataclass
class RegimePeriod:
    """Period of market regime."""
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    regime: MarketRegime
    confidence: float
    characteristics: Dict[str, float]

    def __len__(self) -> int:
        """Return the number of days in this regime period."""
        return (self.end_date - self.start_date).days + 1


class MarketRegimeDetector:
    """Detect market regimes using multiple methods.

    Implements professional regime detection using:
    - Trend analysis (SMA crossovers)
    - Volatility clustering
    - Return distribution analysis
    - Machine learning clustering
    """

    def __init__(
        self,
        trend_window: int = 50,
        volatility_window: int = 20,
        regime_lookback: int = 252,  # 1 year
        min_regime_length: int = 20,  # Minimum 20 trading days
    ):
        """Initialize regime detector.

        Args:
            trend_window: Window for trend calculation (days)
            volatility_window: Window for volatility calculation (days)
            regime_lookback: Historical lookback for regime classification
            min_regime_length: Minimum length for regime classification
        """
        self.trend_window = trend_window
        self.volatility_window = volatility_window
        self.regime_lookback = regime_lookback
        self.min_regime_length = min_regime_length

    def detect_regimes(self, price_data: pd.Series) -> List[RegimePeriod]:
        """Detect market regimes in price data.

        Args:
            price_data: Price series with datetime index

        Returns:
            List of regime periods
        """
        if len(price_data) < self.regime_lookback:
            logger.warning("Insufficient data for regime detection")
            return []

        # Calculate regime indicators
        returns = price_data.pct_change().dropna()
        trend_indicator = self._calculate_trend_indicator(price_data)
        volatility_indicator = self._calculate_volatility_indicator(returns)

        # Combine into regime classification
        regime_series = self._classify_regimes(returns, trend_indicator, volatility_indicator)

        # Group into contiguous regime periods
        regime_periods = self._group_regime_periods(regime_series)

        # Filter short periods
        regime_periods = [p for p in regime_periods if len(p) >= self.min_regime_length]

        logger.info(f"Detected {len(regime_periods)} regime periods")
        return regime_periods

    def _calculate_trend_indicator(self, prices: pd.Series) -> pd.Series:
        """Calculate trend strength indicator.

        Returns:
            Series with trend strength (-1 to 1, negative = downtrend)
        """
        # Simple moving averages
        sma_short = prices.rolling(window=self.trend_window // 2).mean()
        sma_long = prices.rolling(window=self.trend_window).mean()

        # Trend strength as difference between SMAs
        trend_strength = (sma_short - sma_long) / prices.rolling(window=self.trend_window).std()
        trend_strength = trend_strength.fillna(0)

        # Normalize to -1, 1 range
        trend_strength = np.clip(trend_strength, -3, 3) / 3

        return trend_strength

    def _calculate_volatility_indicator(self, returns: pd.Series) -> pd.Series:
        """Calculate volatility indicator.

        Returns:
            Series with volatility relative to historical average
        """
        # Rolling volatility
        vol = returns.rolling(window=self.volatility_window).std() * np.sqrt(252)  # Annualized

        # Historical average volatility
        hist_vol = vol.expanding().mean()

        # Volatility ratio (current vs historical)
        vol_ratio = vol / hist_vol
        vol_ratio = vol_ratio.fillna(1.0)

        return vol_ratio

    def _classify_regimes(self, returns: pd.Series, trend: pd.Series,
                         volatility: pd.Series) -> pd.Series:
        """Classify market regimes using rule-based approach.

        Args:
            returns: Daily returns
            trend: Trend indicator (-1 to 1)
            volatility: Volatility ratio

        Returns:
            Series with MarketRegime values
        """
        regimes = pd.Series(index=returns.index, dtype=object)

        # Thresholds (can be made configurable)
        trend_bull_threshold = 0.2
        trend_bear_threshold = -0.2
        vol_high_threshold = 1.5

        for date in returns.index:
            t = trend.loc[date]
            v = volatility.loc[date]

            if v > vol_high_threshold:
                regime = MarketRegime.HIGH_VOLATILITY
            elif t > trend_bull_threshold:
                regime = MarketRegime.BULL
            elif t < trend_bear_threshold:
                regime = MarketRegime.BEAR
            else:
                regime = MarketRegime.SIDEWAYS

            regimes.loc[date] = regime

        return regimes

    def _group_regime_periods(self, regime_series: pd.Series) -> List[RegimePeriod]:
        """Group consecutive regime classifications into periods.

        Args:
            regime_series: Series with regime classifications

        Returns:
            List of RegimePeriod objects
        """
        periods = []
        current_regime = None
        current_start = None

        for date, regime in regime_series.items():
            if current_regime != regime:
                # End previous period
                if current_regime is not None:
                    period = RegimePeriod(
                        start_date=current_start,
                        end_date=date - pd.Timedelta(days=1),
                        regime=current_regime,
                        confidence=self._calculate_regime_confidence(
                            regime_series[current_start:date], current_regime
                        ),
                        characteristics=self._calculate_regime_characteristics(
                            regime_series[current_start:date]
                        )
                    )
                    periods.append(period)

                # Start new period
                current_regime = regime
                current_start = date

        # Add final period
        if current_regime is not None:
            period = RegimePeriod(
                start_date=current_start,
                end_date=regime_series.index[-1],
                regime=current_regime,
                confidence=self._calculate_regime_confidence(
                    regime_series[current_start:], current_regime
                ),
                characteristics=self._calculate_regime_characteristics(
                    regime_series[current_start:]
                )
            )
            periods.append(period)

        return periods

    def _calculate_regime_confidence(self, period_regimes: pd.Series,
                                   regime_type: MarketRegime) -> float:
        """Calculate confidence in regime classification.

        Args:
            period_regimes: Regimes for this period
            regime_type: Expected regime type

        Returns:
            Confidence score (0-1)
        """
        if len(period_regimes) == 0:
            return 0.0

        # Percentage of days matching expected regime
        matching_days = (period_regimes == regime_type).sum()
        confidence = matching_days / len(period_regimes)

        return confidence

    def _calculate_regime_characteristics(self, period_regimes: pd.Series) -> Dict[str, float]:
        """Calculate characteristics of regime period.

        Args:
            period_regimes: Regimes for this period

        Returns:
            Dictionary of characteristics
        """
        total_days = len(period_regimes)

        if total_days == 0:
            return {}

        # Regime distribution
        regime_counts = period_regimes.value_counts()
        characteristics = {}

        for regime in MarketRegime:
            characteristics[f"{regime.value}_pct"] = regime_counts.get(regime, 0) / total_days

        characteristics["length_days"] = total_days
        characteristics["dominant_regime"] = regime_counts.idxmax().value if not regime_counts.empty else None

        return characteristics

    def analyze_regime_performance(self, strategy_returns: pd.Series,
                                 benchmark_returns: pd.Series,
                                 regime_periods: List[RegimePeriod]) -> Dict[str, Dict[str, float]]:
        """Analyze strategy performance across different regimes.

        Args:
            strategy_returns: Strategy daily returns
            benchmark_returns: Benchmark daily returns
            regime_periods: Detected regime periods

        Returns:
            Dictionary with performance by regime
        """
        performance_by_regime = {}

        for regime in MarketRegime:
            regime_dates = []
            for period in regime_periods:
                if period.regime == regime:
                    date_range = pd.date_range(period.start_date, period.end_date, freq='D')
                    regime_dates.extend(date_range)

            if not regime_dates:
                performance_by_regime[regime.value] = {
                    "total_return": 0.0,
                    "volatility": 0.0,
                    "sharpe_ratio": 0.0,
                    "max_drawdown": 0.0,
                    "benchmark_return": 0.0,
                    "alpha": 0.0,
                    "sample_size": 0
                }
                continue

            # Filter returns for this regime
            regime_mask = strategy_returns.index.isin(regime_dates)
            regime_strategy_returns = strategy_returns[regime_mask]
            regime_benchmark_returns = benchmark_returns[regime_mask]

            if len(regime_strategy_returns) == 0:
                continue

            # Calculate metrics
            total_return = (1 + regime_strategy_returns).prod() - 1
            volatility = regime_strategy_returns.std() * np.sqrt(252)
            sharpe = regime_strategy_returns.mean() / regime_strategy_returns.std() * np.sqrt(252) if regime_strategy_returns.std() > 0 else 0.0

            # Max drawdown
            cum_returns = (1 + regime_strategy_returns).cumprod()
            rolling_max = cum_returns.expanding().max()
            drawdowns = (cum_returns - rolling_max) / rolling_max
            max_dd = abs(drawdowns.min()) if len(drawdowns) > 0 else 0.0

            # Benchmark comparison
            benchmark_return = (1 + regime_benchmark_returns).prod() - 1
            alpha = total_return - benchmark_return

            performance_by_regime[regime.value] = {
                "total_return": total_return,
                "volatility": volatility,
                "sharpe_ratio": sharpe,
                "max_drawdown": max_dd,
                "benchmark_return": benchmark_return,
                "alpha": alpha,
                "sample_size": len(regime_strategy_returns)
            }

        return performance_by_regime

    def cluster_based_regime_detection(self, price_data: pd.Series,
                                     n_regimes: int = 4) -> List[RegimePeriod]:
        """Alternative regime detection using unsupervised clustering.

        Args:
            price_data: Price series
            n_regimes: Number of regime clusters

        Returns:
            List of regime periods using clustering
        """
        # Calculate features for clustering
        returns = price_data.pct_change().dropna()
        features = pd.DataFrame({
            'returns': returns,
            'volatility': returns.rolling(20).std(),
            'trend': price_data.pct_change(50).rolling(10).mean(),
        }).dropna()

        # Normalize features
        features_normalized = (features - features.mean()) / features.std()

        # Cluster
        kmeans = KMeans(n_clusters=n_regimes, random_state=42, n_init=10)
        clusters = kmeans.fit_predict(features_normalized.values)

        # Map clusters to regimes (simplified mapping)
        cluster_regime_map = self._map_clusters_to_regimes(kmeans.cluster_centers_, features.columns)

        # Create regime series
        regime_series = pd.Series(index=features.index, dtype=object)
        for i, cluster in enumerate(clusters):
            regime_series.iloc[i] = cluster_regime_map[cluster]

        # Group into periods
        regime_periods = self._group_regime_periods(regime_series)

        return regime_periods

    def _map_clusters_to_regimes(self, cluster_centers: np.ndarray,
                               feature_names: pd.Index) -> Dict[int, MarketRegime]:
        """Map cluster centers to market regimes.

        Args:
            cluster_centers: Cluster center coordinates
            feature_names: Names of features used

        Returns:
            Mapping from cluster ID to regime
        """
        mapping = {}

        for cluster_id, center in enumerate(cluster_centers):
            # Simple rule-based mapping based on feature values
            return_idx = feature_names.get_loc('returns')
            vol_idx = feature_names.get_loc('volatility')
            trend_idx = feature_names.get_loc('trend')

            returns_score = center[return_idx]
            vol_score = center[vol_idx]
            trend_score = center[trend_idx]

            if vol_score > 0.5:  # High volatility
                regime = MarketRegime.HIGH_VOLATILITY
            elif trend_score > 0.2 and returns_score > 0:  # Strong uptrend
                regime = MarketRegime.BULL
            elif trend_score < -0.2 and returns_score < 0:  # Strong downtrend
                regime = MarketRegime.BEAR
            else:  # Sideways
                regime = MarketRegime.SIDEWAYS

            mapping[cluster_id] = regime

        return mapping
