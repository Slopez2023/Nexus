# 🔧 NEXUS Development Guide

## 📋 **Project Overview**

**Phase 1 Complete**: NEXUS has a professional infrastructure foundation with PostgreSQL database, RESTful API, type-safe configuration, monitoring, and automated testing.

**Current Status**: Infrastructure ready, preparing for Phase 2 (trading strategies).

**Architecture**: Python 3.11+ with FastAPI, PostgreSQL, Redis, Docker containerization.

## 🚀 **Quick Start**

### **Prerequisites**
- **Python 3.11+** (required for full feature support)
- **PostgreSQL 15+** (local or Docker)
- **Docker & Docker Compose** (recommended for infrastructure)
- **Git** for version control
- **4GB+ RAM** recommended

### **Development Setup**
```bash
# Clone repository
git clone https://github.com/Slopez2023/Nexus.git
cd nexus/new_project

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Option 1: Docker infrastructure (recommended)
docker-compose up -d

# Option 2: Local PostgreSQL
brew install postgresql@15  # macOS
brew services start postgresql@15
createdb nexus_trading

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Initialize database
psql -d nexus_trading -f database_schema.sql

# Verify setup
python -c "from nexus.core.database import init_database; db = init_database(); print('✅ NEXUS ready!')"
```

### **Alternative: Full Docker Setup**
```bash
# Run everything in containers
docker-compose -f docker-compose.full.yml up -d

# Access services
docker-compose exec postgres psql -U nexus_user -d nexus_trading
```

## 🧪 **Testing**

### **Comprehensive Test Suite**
```bash
# Run all tests with coverage
pytest tests/ -v --cov=nexus --cov-report=html --cov-report=term

# Run specific component tests
pytest tests/core/test_config_manager.py -v    # Configuration tests
pytest tests/core/test_data_api.py -v          # API tests
pytest tests/core/ -v                          # All core tests

# Run with performance profiling
pytest tests/ --durations=10 --cov=nexus
```

### **Database Testing**
```bash
# Create isolated test database
python scripts/manage_config.py generate testing --output config.testing.json
python nexus/core/test_database.py create --schema database_schema.sql

# Run database-specific tests
pytest tests/ -k "database" -v
```

### **Integration Testing**
```bash
# Test full system integration
python -c "
from nexus.core.database import init_database
from nexus.monitoring.health_monitor import HealthMonitor

# Test database connection
db = init_database()
health = db.health_check()
print(f'Database: {health}')

# Test monitoring system
monitor = HealthMonitor()
system_health = monitor.perform_full_health_check()
print(f'System Health: {system_health.status.value}')
"
```

### **Test Coverage Requirements**
- **Current Coverage**: 30%+ (expanding with Phase 2)
- **Critical Paths**: All infrastructure, configuration, database operations
- **CI/CD**: Automated testing on merge requests
- **Performance**: <100ms for cached operations, <2s for fresh data

## 🔍 **Code Quality**

### **Linting & Formatting**
```bash
# Automated code quality checks
flake8 nexus/ tests/ scripts/ --max-line-length=88
black nexus/ tests/ scripts/ --check
mypy nexus/ --ignore-missing-imports

# Auto-fix formatting
black nexus/ tests/ scripts/
```

### **Security Scanning**
```bash
# Security vulnerability checks
bandit -r nexus/ -f json -o security_report.json
safety check --output text
```

## 🏗️ **Development Workflow**

### **Daily Development Cycle**
```bash
# 1. Pull latest changes
git pull origin main

# 2. Create feature branch
git checkout -b feature/your-feature-name

# 3. Make changes with tests
# ... development work ...

# 4. Run quality checks
pytest tests/ -v
black nexus/ tests/ scripts/
flake8 nexus/ tests/ scripts/

# 5. Commit with conventional format
git add .
git commit -m "feat: add new feature description"

# 6. Push and create PR
git push origin feature/your-feature-name
```

### **Configuration Management**
```bash
# View current configuration
python scripts/manage_config.py show

# Update configuration safely
python scripts/manage_config.py update database.port 5433 --user "developer_name"

# Validate configuration
python scripts/manage_config.py validate
```

### **System Monitoring**
```bash
# Health check
python scripts/monitor_system.py

# Continuous monitoring
python scripts/monitor_system.py --continuous --interval 60

# Database backup
python scripts/backup_database.py create --type full
```

## 🚀 **API Development**

### **Data API Usage**
```bash
# Start API server
python run_api.py

# API endpoints available at http://127.0.0.1:8000
# OpenAPI docs at http://127.0.0.1:8000/docs

# Example API calls
curl "http://127.0.0.1:8000/api/v1/data/AAPL?start_date=2024-01-01&end_date=2024-01-02"
curl "http://127.0.0.1:8000/api/v1/health"
curl "http://127.0.0.1:8000/api/v1/sources"
```

## 🐳 **Docker Development**

### **Containerized Workflow**
```bash
# Start infrastructure
docker-compose up -d

# Run tests in container
docker-compose exec nexus pytest tests/ -v

# View logs
docker-compose logs -f postgres
docker-compose logs -f redis

# Access database
docker-compose exec postgres psql -U nexus_user -d nexus_trading

# Clean up
docker-compose down -v  # Remove volumes too
```

## 📊 **Performance Monitoring**

### **Built-in Metrics**
- **API Response Times**: Tracked automatically
- **Database Query Performance**: Connection pooling metrics
- **Cache Hit Rates**: Redis performance monitoring
- **System Resources**: CPU, memory, disk usage

## 🔧 **Troubleshooting**

### **Common Issues**

#### **Database Connection Failed**
```bash
# Check if PostgreSQL is running
brew services list | grep postgresql

# Or with Docker
docker-compose ps

# Reset database
psql postgres -c "DROP DATABASE nexus_trading;"
createdb nexus_trading
psql -d nexus_trading -f database_schema.sql
```

#### **Configuration Errors**
```bash
# Validate configuration
python scripts/manage_config.py validate

# Check environment variables
env | grep -E "(DB_|API_|LOG_)"

# Reset configuration
cp .env.example .env
# Edit .env with correct values
```

#### **Test Failures**
```bash
# Run specific failing test
pytest tests/core/test_config_manager.py::TestConfigManager::test_specific_method -v -s

# Debug with pdb
pytest tests/ --pdb --tb=short
```

## 📚 **Architecture Guidelines**

### **Code Organization**
```
nexus/
├── core/                 # Infrastructure layer
│   ├── config_manager.py # ✅ Type-safe configuration
│   ├── database.py      # ✅ Connection management
│   ├── data_api.py      # ✅ RESTful API
│   └── logging_config.py # ✅ Enhanced logging
├── monitoring/          # ✅ Health monitoring
├── scripts/             # ✅ Management utilities
└── tests/               # ✅ Comprehensive testing
```

### **Design Patterns Used**
- **Factory Pattern**: Data source creation
- **Observer Pattern**: Health monitoring alerts
- **Context Manager**: Safe database connections
- **Strategy Pattern**: Configurable algorithms
- **Repository Pattern**: Data access abstraction

---

**Phase 1 Infrastructure: Complete** ✅
**Ready for Phase 2: Trading Logic Development** 🚀
