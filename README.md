# 🧠 NEXUS AI Trading System

**An intelligent algorithmic trading platform built with understanding as the core principle.**

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://github.com/Slopez2023/Nexus/workflows/CI/badge.svg)](https://github.com/Slopez2023/Nexus/actions)
[![Python Versions](https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10%20%7C%203.11-blue)](https://python.org)

## 📊 **Current Status: Phase 1+ Advanced Validation Complete**

**✅ FULLY IMPLEMENTED:**
- **Data Pipeline**: Multi-source data aggregation with quality validation
- **Database Layer**: PostgreSQL with time-series optimization
- **API Hub**: RESTful data access with caching and normalization
- **Configuration**: Type-safe configuration management with audit logging
- **Infrastructure**: Docker containers, monitoring, backups, testing
- **🔬 Advanced Backtesting Engine**: Complete professional validation suite
  - Walk-forward analysis with rolling optimization windows
  - Monte Carlo simulation (10,000 bootstrap tests)
  - Multi-regime testing (bull/bear/sideways market performance)
  - Holdout validation (unseen data overfitting detection)
  - Comprehensive reporting with actionable insights

**🚧 NEXT: Phase 2 - Trading Strategy Development**

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- Docker (optional, for containerized setup)
- pip

### Installation

1. **Clone the repository**
```bash
   git clone https://github.com/yourusername/nexus.git
   cd nexus
```

2. **Set up virtual environment**
```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up infrastructure**
   ```bash
   # Option 1: Local PostgreSQL
   brew install postgresql@15  # macOS
   brew services start postgresql@15
   createdb nexus_trading

   # Option 2: Docker (recommended for development)
   docker-compose up -d
   ```

5. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and settings
   ```

6. **Initialize database**
   ```bash
   psql -d nexus_trading -f database_schema.sql
   ```

### Basic Usage

**Current Phase**: Infrastructure complete, trading logic in development.

```python
# Example: Initialize NEXUS components
from nexus.core.config_manager import get_app_config
from nexus.core.database import init_database
from nexus.monitoring.health_monitor import HealthMonitor

# Load configuration
config = get_app_config()
print(f"NEXUS Environment: {config.environment}")

# Initialize database
db = init_database()
health = db.health_check()
print(f"Database Status: {health['status']}")

# Check system health
monitor = HealthMonitor()
system_health = monitor.perform_full_health_check()
print(f"System Health: {system_health.status.value.upper()}")

# Advanced Validation Example
from nexus.backtesting import ValidationRunner

def momentum_strategy(price_data, formation_days=126):
    # Simple momentum strategy implementation
    signals = pd.Series(index=price_data.index, dtype=float)
    for i in range(formation_days, len(price_data)):
        current_date = price_data.index[i]
        formation_data = price_data.iloc[i - formation_days:i + 1]
        momentum = (formation_data.iloc[-1] / formation_data.iloc[0]) - 1
        signals.loc[current_date] = 1.0 if momentum > 0 else -1.0
    return signals.fillna(0.0)

# Run comprehensive validation
validator = ValidationRunner()
report = validator.run_comprehensive_validation(
    strategy_func=momentum_strategy,
    price_data=market_data,
    parameter_ranges={'formation_days': (50, 200)},
    strategy_name="Momentum Strategy"
)

# Print executive summary
validator.report_generator.print_executive_summary(report)
```

### Data API Server

NEXUS includes a unified Data API server for accessing market data:

```bash
# Start the API server
python run_api.py

# Server runs on http://127.0.0.1:8000
# API docs available at http://127.0.0.1:8000/docs
```

**API Endpoints:**
- `GET /api/v1/health` - Server health status
- `GET /api/v1/sources` - Available data sources
- `GET /api/v1/data/{symbol}?start_date=...&end_date=...` - Historical data
- `GET /api/v1/data/{symbol}/realtime` - Real-time quotes

### Configuration Management

```bash
# View current configuration
python scripts/manage_config.py show

# Update configuration
python scripts/manage_config.py update database.port 5433

# Export configuration
python scripts/manage_config.py export --format yaml
```

### Health Monitoring

```bash
# Run health checks
python scripts/monitor_system.py

# Continuous monitoring
python scripts/monitor_system.py --continuous --interval 60
```

## 📊 What is NEXUS?

NEXUS is an AI-powered algorithmic trading system designed for clarity and safety. Unlike black-box systems, every component serves a clear, understandable purpose:

- **🤖 AI Agents**: Research strategies, assess risk, and provide market insights
- **📈 Strategy Framework**: Modular trading strategies with clear entry/exit rules
- **🔬 Advanced Validation Suite**: Professional-grade backtesting with scientific rigor
  - **Walk-Forward Analysis**: Rolling optimization windows prevent overfitting
  - **Monte Carlo Simulation**: 10,000 bootstrap tests assess statistical robustness
  - **Multi-Regime Testing**: Performance validation across bull/bear/sideways markets
  - **Holdout Validation**: Unseen data testing detects generalization issues
  - **Comprehensive Reporting**: Actionable insights with deployment recommendations
- **🛡️ Risk Management**: Multi-layered safety controls at every level
- **📊 Monitoring**: Real-time performance tracking and alerting

### Key Principles
- **Understanding First**: Every decision is explainable
- **Safety First**: Risk controls before features
- **Validation Everything**: Extensive backtesting required
- **Start Simple**: Build what you understand, expand gradually

### Advanced Validation Features
NEXUS includes professional-grade validation methods to prevent overfitting and ensure strategy robustness:

- **Walk-Forward Analysis**: Rolling time windows with parameter optimization and out-of-sample testing
- **Monte Carlo Simulation**: 10,000 bootstrap tests with comprehensive confidence intervals and risk metrics
- **Multi-Regime Testing**: Performance analysis across bull, bear, sideways, and high-volatility markets
- **Holdout Validation**: Unseen data testing with overfitting detection and generalization assessment
- **Comprehensive Reports**: Automated synthesis of all validation results with actionable recommendations

## 🏗️ Architecture

```
NEXUS/
├── nexus/                    # Core system
│   ├── core/                # Infrastructure layer
│   │   ├── config_manager.py # Type-safe configuration management
│   │   ├── database.py      # PostgreSQL connection & operations
│   │   ├── data_api.py      # RESTful data API with caching
│   │   ├── logging_config.py # Enhanced logging system
│   │   └── test_database.py # Isolated testing environment
│   ├── monitoring/          # Health monitoring & alerting
│   │   └── health_monitor.py # System health checks
│   ├── strategies/          # Trading strategies (Phase 2)
│   ├── backtesting/         # Validation engine (Phase 2)
│   ├── risk/                # Risk management (Phase 2)
│   └── agents/              # AI analysis agents (Phase 4)
├── scripts/                 # Management scripts
│   ├── backup_database.py   # Database backup utilities
│   ├── manage_config.py     # Configuration management CLI
│   ├── monitor_system.py    # Health monitoring CLI
│   └── run_api.py          # API server launcher
├── tests/                   # Comprehensive test suite
├── docs/                    # Documentation
├── docker-compose.yml       # Containerized infrastructure
├── config.json             # Configuration file
├── database_schema.sql     # Database schema
└── requirements.txt        # Dependencies
```

## 🧪 Development

### 📚 Development Guide
For comprehensive development instructions, testing procedures, and maintenance guidelines, see:
- **[Development Guide](docs/DEVELOPMENT_GUIDE.md)** - Complete setup, testing, and deployment instructions
- **[Phase 1 Implementation](docs/PHASE1_IMPLEMENTATION.md)** - Current implementation details
- **[Roadmap](docs/ROADMAP.md)** - Development roadmap and milestones

### Running Tests

**Full Test Suite:**
```bash
# Run all tests with coverage
pytest tests/ -v --cov=nexus --cov-report=html

# Run specific test categories
pytest tests/core/ -v              # Core infrastructure tests
pytest tests/core/test_config_manager.py -v  # Configuration tests
pytest tests/core/test_data_api.py -v       # API tests

# Run with different Python versions (CI)
tox
```

**Code Quality Checks:**
```bash
# Linting and formatting
flake8 nexus/ tests/ scripts/
black nexus/ tests/ scripts/
mypy nexus/ --ignore-missing-imports

# Security checks
bandit -r nexus/
safety check
```

**Database Tests:**
```bash
# Create test database
python scripts/manage_config.py generate testing --output config.testing.json
python nexus/core/test_database.py create --schema database_schema.sql

# Run database-specific tests
pytest tests/ -k "database" -v
```

### Code Quality
```bash
# Lint code
flake8 nexus/ tests/

# Format code
black nexus/ tests/

# Type check
mypy nexus/ --ignore-missing-imports
```

### Documentation
```bash
# Build docs
cd docs
make html

# View docs
open _build/html/index.html
```

## 📚 Documentation

- **[Architecture Guide](docs/ARCHITECTURE.md)**: System design and component relationships
- **[Development Roadmap](docs/ROADMAP.md)**: Project phases and success criteria
- **[API Reference](docs/_build/html/index.html)**: Complete API documentation
- **[Contributing Guide](docs/CONTRIBUTING.md)**: How to contribute

## 🎯 Roadmap Highlights

### Phase 1 (Current): Core Infrastructure ✅
- Data pipeline with validation
- Strategy framework
- Backtesting engine

### Phase 2: First Trading Strategy
- RSI-based strategy implementation
- Comprehensive backtesting
- Risk management integration

### Phase 3: Advanced Features
- Live execution system
- Enhanced risk controls
- Performance monitoring

### Phase 4: AI Agent Integration
- Market analysis agents
- Strategy research agents
- Risk assessment agents

### Phase 5: Live Deployment
- Paper trading validation
- Micro live deployment
- Gradual scaling to profits

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](docs/CONTRIBUTING.md) for details.

**Quick Start for Contributors:**
1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes with tests
4. Run the full test suite: `pytest`
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

**This software is for educational and research purposes only.** Trading cryptocurrencies and other financial instruments involves substantial risk of loss. Past performance does not guarantee future results. Always test strategies extensively and never risk more than you can afford to lose.

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/nexus/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/nexus/discussions)
- **Documentation**: [Read the Docs](https://nexus.readthedocs.io/)

---

*Built with understanding, validated with rigor, deployed with caution.*
