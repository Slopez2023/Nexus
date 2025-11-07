"""Local Data API Hub - Unified market data access for NEXUS.

Provides a single FastAPI endpoint that aggregates data from multiple sources,
with caching, normalization, and consistent formatting.
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
import pandas as pd

from nexus.core.data import DataManager, DataSourceResult, DataQualityMetrics
from nexus.core.logging import get_logger


@dataclass
class CacheEntry:
    """Cache entry with TTL."""
    data: Any
    timestamp: float
    ttl: int  # seconds


class DataCache:
    """Simple in-memory cache with TTL. Upgrade to Redis later."""

    def __init__(self):
        self.cache: Dict[str, CacheEntry] = {}
        self.logger = get_logger(__name__)

    def get(self, key: str) -> Optional[Any]:
        """Get cached data if not expired."""
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry.timestamp < entry.ttl:
                return entry.data
            else:
                # Expired, remove it
                del self.cache[key]
        return None

    def set(self, key: str, data: Any, ttl: int):
        """Set cached data with TTL."""
        self.cache[key] = CacheEntry(data=data, timestamp=time.time(), ttl=ttl)

    def clear_expired(self):
        """Remove expired entries."""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.cache.items()
            if current_time - entry.timestamp >= entry.ttl
        ]
        for key in expired_keys:
            del self.cache[key]
        if expired_keys:
            self.logger.info(f"Cleared {len(expired_keys)} expired cache entries")


class DataNormalizer:
    """Normalize data from different sources to consistent format."""

    @staticmethod
    def normalize_historical_data(data: pd.DataFrame) -> Dict[str, Any]:
        """Normalize historical OHLCV data."""
        if data.empty:
            return {"data": [], "metadata": {"count": 0, "empty": True}}

        # Ensure consistent column order and naming
        required_cols = ["Open", "High", "Low", "Close", "Volume"]
        available_cols = [col for col in required_cols if col in data.columns]

        # Convert to records format with proper timestamp handling
        df_copy = data[available_cols].copy()
        df_copy['timestamp'] = df_copy.index
        records = df_copy.reset_index(drop=True).to_dict('records')

        # Convert timestamps to ISO format
        for record in records:
            if isinstance(record['timestamp'], pd.Timestamp):
                record['timestamp'] = record['timestamp'].isoformat()

        return {
            "data": records,
            "metadata": {
                "count": len(records),
                "columns": available_cols,
                "date_range": {
                    "start": data.index.min().isoformat() if len(data) > 0 else None,
                    "end": data.index.max().isoformat() if len(data) > 0 else None
                },
                "empty": False
            }
        }

    @staticmethod
    def normalize_realtime_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize real-time quote data."""
        # Placeholder - implement based on source formats
        return {
            "symbol": data.get("symbol", "unknown"),
            "price": data.get("price", 0.0),
            "timestamp": datetime.now().isoformat(),
            "source": data.get("source", "unknown")
        }


class DataAPI:
    """Local Data API Hub using FastAPI."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = get_logger(__name__)

        # Initialize components
        self.data_manager = DataManager(config)
        self.cache = DataCache()
        self.normalizer = DataNormalizer()

        # Create FastAPI app
        self.app = FastAPI(
            title="NEXUS Data API",
            description="Unified market data access for NEXUS trading system",
            version="1.0.0"
        )

        # Setup routes
        self._setup_routes()

        # Cache cleanup task (started when server runs)
        self._cleanup_task = None

    def _setup_routes(self):
        """Set up API routes."""

        @self.app.get("/api/v1/health")
        async def health_check():
            """Health check endpoint."""
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0"
            }

        @self.app.get("/api/v1/sources")
        async def get_sources():
            """Get available data sources."""
            sources_info = []
            for source in self.data_manager.sources:
                sources_info.append({
                    "name": source.name,
                    "priority": source.priority,
                    "available": source.is_available()
                })
            return {"sources": sources_info}

        @self.app.get("/api/v1/data/{symbol}")
        async def get_historical_data(
            symbol: str,
            start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
            end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
            source: Optional[str] = Query(None, description="Preferred data source")
        ):
            """Get historical market data for a symbol."""
            try:
                # Create cache key
                cache_key = f"historical_{symbol}_{start_date}_{end_date}_{source or 'auto'}"

                # Check cache first
                cached_result = self.cache.get(cache_key)
                if cached_result:
                    self.logger.info(f"Cache hit for {symbol}")
                    return cached_result

                # Fetch data
                self.logger.info(f"Fetching historical data for {symbol}")
                result = await self.data_manager.fetch_historical_data_async(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    use_ai_analysis=False
                )

                if not result.get("recommended_data"):
                    raise HTTPException(status_code=404, detail=f"No data found for {symbol}")

                # Convert back to DataFrame for normalization
                data_df = pd.DataFrame.from_dict(result["recommended_data"])

                # Normalize response
                normalized = self.normalizer.normalize_historical_data(data_df)

                # Add metadata
                response = {
                    **normalized,
                    "symbol": symbol,
                    "source": result.get("best_source"),
                    "quality_score": result.get("quality_assessment", {}).get("overall_score"),
                    "fetched_at": datetime.now().isoformat()
                }

                # Cache for 1 hour
                self.cache.set(cache_key, response, ttl=3600)

                return response

            except Exception as e:
                self.logger.error(f"Error fetching historical data for {symbol}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/v1/data/{symbol}/realtime")
        async def get_realtime_data(symbol: str):
            """Get real-time quote for a symbol."""
            try:
                # For now, return latest historical data as proxy
                # TODO: Implement real-time data fetching
                cache_key = f"realtime_{symbol}"

                cached_result = self.cache.get(cache_key)
                if cached_result:
                    return cached_result

                # Get recent data (last 7 days) as proxy for real-time
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=7)

                result = await self.data_manager.fetch_historical_data_async(
                    symbol=symbol,
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                    use_ai_analysis=False
                )

                if result.get("recommended_data"):
                    data_df = pd.DataFrame.from_dict(result["recommended_data"])
                    if not data_df.empty:
                        # Get latest row
                        latest = data_df.iloc[-1]
                        response = {
                            "symbol": symbol,
                            "price": latest.get("Close", 0.0),
                            "timestamp": latest.name.isoformat() if hasattr(latest, 'name') else datetime.now().isoformat(),
                            "source": result.get("best_source", "unknown"),
                            "type": "proxy_realtime"  # Indicates this is historical proxy
                        }

                        # Cache for 30 seconds
                        self.cache.set(cache_key, response, ttl=30)
                        return response

                raise HTTPException(status_code=404, detail=f"No recent data for {symbol}")

            except Exception as e:
                self.logger.error(f"Error fetching realtime data for {symbol}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

    async def _cache_cleanup_loop(self):
        """Background task to clean expired cache entries."""
        while True:
            await asyncio.sleep(300)  # Clean every 5 minutes
            self.cache.clear_expired()

    def run_server(self, host: str = "127.0.0.1", port: int = 8000):
        """Run the API server."""
        import uvicorn
        self.logger.info(f"Starting Data API server on {host}:{port}")

        # Start background cache cleanup task
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._cleanup_task = loop.create_task(self._cache_cleanup_loop())

        uvicorn.run(self.app, host=host, port=port)


# Global API instance for easy access
_api_instance: Optional[DataAPI] = None

def get_data_api(config: Optional[Dict[str, Any]] = None) -> DataAPI:
    """Get or create the global DataAPI instance."""
    global _api_instance
    if _api_instance is None:
        _api_instance = DataAPI(config)
    return _api_instance

def create_app(config: Optional[Dict[str, Any]] = None) -> FastAPI:
    """Create FastAPI app instance for external use."""
    api = get_data_api(config)
    return api.app
