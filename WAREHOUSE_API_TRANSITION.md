# Market Data Warehouse API Integration Plan

**Document Version**: 1.0  
**Last Updated**: 2025-11-10  
**Status**: In Progress  

## Executive Summary

This document outlines the professional transition strategy to make the Market Data Warehouse API the primary data source for NEXUS while maintaining system integrity, backward compatibility, and production reliability.

---

## Architecture Overview

### Current State
- Multiple data sources: Polygon.io (Massive), yfinance, CoinGecko
- Data quality assessment and source prioritization
- FastAPI-based local data hub with caching

### Target State
- Warehouse API as primary data source
- Backward-compatible adapter layer
- Gradual, feature-flagged rollout
- Enhanced observability and monitoring

---

## Implementation Phases

### Phase 1: Foundation & Integration Layer (Days 1-3)

**Objectives:**
- Create Warehouse API client with production-grade reliability
- Establish data model compatibility
- Build comprehensive test coverage
- Zero impact to existing code

**Deliverables:**
1. `integrations/warehouse_api_client.py` - Async HTTP client with:
   - Retry logic (exponential backoff)
   - Circuit breaker pattern
   - Rate limiting
   - Connection pooling
   - Comprehensive error handling

2. `integrations/warehouse_api_adapter.py` - Adapter converting Warehouse API responses to existing data models

3. `core/config_manager.py` - Enhanced configuration for Warehouse API

4. Comprehensive unit tests with mocking

### Phase 2: Integration with Existing Pipeline (Days 4-6)

**Objectives:**
- Integrate Warehouse API into current data flow
- Maintain all existing data sources
- Implement feature flag for controlled rollout
- Parallel testing with existing sources

**Deliverables:**
1. Modified `core/data/data.py` - Add `WarehouseDataSource` class

2. Feature flag system in config:
   ```
   warehouse_api:
     enabled: true
     primary: false  # false = use old sources with warehouse as fallback
     priority: 1     # when enabled as primary
   ```

3. Monitoring and comparison endpoints

4. Integration tests

### Phase 3: Validation & Comparison (Days 7-9)

**Objectives:**
- Run backtests with both data sources
- Compare results and validate consistency
- Document any discrepancies
- Performance profiling

**Deliverables:**
1. Validation test suite comparing data sources

2. Performance benchmarks

3. Data quality analysis report

4. Migration readiness checklist

### Phase 4: Gradual Production Migration (Days 10-14)

**Objectives:**
- Enable Warehouse API as primary source
- Monitor metrics closely
- Keep fallback to old sources
- Full deprecation path

**Deliverables:**
1. Activate feature flag in production

2. Real-time monitoring dashboard

3. Automated alerts for data quality issues

4. Deprecation timeline and documentation

### Phase 5: Cleanup & Optimization (Days 15-20)

**Objectives:**
- Remove legacy data sources
- Optimize Warehouse API usage
- Performance tuning
- Final documentation

**Deliverables:**
1. Cleaned codebase

2. Updated documentation

3. Performance optimization report

4. Knowledge transfer documentation

---

## Code Architecture

```
src/nexus/integrations/
├── __init__.py
├── warehouse_api_client.py      # HTTP client with retry/circuit breaker
├── warehouse_api_adapter.py     # Data model conversion
└── warehouse_api_monitor.py     # Health/metrics collection

Enhanced existing files:
├── core/config_manager.py       # Add warehouse_api config section
├── core/data/data.py            # Add WarehouseDataSource class
├── core/data_api.py             # Enhanced with feature flags
└── monitoring/health_monitor.py # Warehouse API health tracking

New test files:
├── tests/integration/test_warehouse_api_integration.py
├── tests/integration/test_warehouse_api_vs_legacy.py
├── tests/unit/test_warehouse_api_client.py
└── tests/unit/test_warehouse_api_adapter.py
```

---

## Configuration Changes

### .env additions
```
# Warehouse API Configuration
WAREHOUSE_API_URL=http://localhost:8000
WAREHOUSE_API_ENABLED=false
WAREHOUSE_API_PRIMARY=false
WAREHOUSE_API_TIMEOUT=30
WAREHOUSE_API_RETRY_ATTEMPTS=3
WAREHOUSE_API_RETRY_BACKOFF=1.5
```

### config.json additions
```json
{
  "warehouse_api": {
    "url": "${WAREHOUSE_API_URL}",
    "enabled": false,
    "primary": false,
    "timeout_seconds": 30,
    "retry": {
      "max_attempts": 3,
      "initial_backoff_ms": 100,
      "max_backoff_ms": 30000,
      "backoff_multiplier": 1.5
    },
    "circuit_breaker": {
      "failure_threshold": 5,
      "success_threshold": 2,
      "timeout_seconds": 60
    },
    "cache": {
      "enabled": true,
      "ttl_seconds": 3600
    }
  }
}
```

---

## Testing Strategy

### Unit Tests
- API client initialization and configuration
- Request/response handling
- Error scenarios and retries
- Data model conversion
- Cache behavior

### Integration Tests
- Data fetch from Warehouse API
- Comparison with legacy sources
- End-to-end data pipeline
- Feature flag behavior

### Data Quality Tests
- OHLCV data consistency
- Missing bar detection
- Timestamp validation
- Volume consistency
- Historical data continuity

### Performance Tests
- Latency benchmarking
- Throughput comparison
- Memory usage profiling
- Cache effectiveness

---

## Monitoring & Observability

### Metrics to Track
- API response times (p50, p95, p99)
- Error rates by type
- Cache hit rate
- Data quality scores
- Fallback activation count
- Request volume

### Alerts
- API unavailability > 5 minutes
- Error rate > 5%
- Data quality score < 90%
- Circuit breaker tripped
- Latency p95 > 5 seconds

### Dashboards
- Real-time API health
- Data source comparison
- Performance trends
- Error analysis

---

## Risk Mitigation

### Risk: Data Inconsistencies
- **Mitigation**: Parallel testing phase, data quality validation, comparison suite

### Risk: Performance Degradation
- **Mitigation**: Performance profiling, caching strategy, circuit breaker limits

### Risk: Availability Issues
- **Mitigation**: Fallback to legacy sources, circuit breaker, retry logic

### Risk: Configuration Errors
- **Mitigation**: Feature flags, staged rollout, easy rollback

---

## Success Criteria

✅ Phase 1: 100% test coverage for new code, zero breaking changes  
✅ Phase 2: Warehouse API integrated with feature flag OFF by default  
✅ Phase 3: Data validation passed, performance benchmarks acceptable  
✅ Phase 4: Feature flag ON in staging, metrics monitoring active  
✅ Phase 5: Legacy sources removed, documentation updated, team trained  

---

## Timeline

| Phase | Duration | Key Dates |
|-------|----------|-----------|
| Phase 1 | 3 days | Nov 10-12 |
| Phase 2 | 3 days | Nov 13-15 |
| Phase 3 | 3 days | Nov 16-18 |
| Phase 4 | 5 days | Nov 19-23 |
| Phase 5 | 6 days | Nov 24-29 |

---

## Rollback Plan

### If Critical Issues Detected
1. Set `warehouse_api.primary: false` in config
2. Restart services
3. Monitoring confirms fallback to legacy sources
4. Root cause analysis
5. Fix deployment
6. Gradual retry

### Rollback Success Criteria
- All endpoints responding normally
- Data quality scores > 95%
- Error rates < 1%
- All tests passing

---

## Sign-Off & Approval

**Document Owner**: System Architecture  
**Reviewed By**: [Pending]  
**Approved By**: [Pending]  
**Last Review Date**: [Pending]
