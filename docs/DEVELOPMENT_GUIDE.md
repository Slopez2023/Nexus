# 🔧 NEXUS Development Guide

## 📋 **Project Overview**

NEXUS is an AI-powered algorithmic trading system built with Python. This guide ensures consistent development, testing, and deployment across all environments.

## 🚀 **Quick Start**

### **Prerequisites**
- Python 3.8+ (tested on 3.8, 3.9, 3.10, 3.11)
- Git
- Virtual environment tool (venv recommended)

### **Initial Setup**
```bash
# Clone repository
git clone https://github.com/Slopez2023/Nexus.git
cd nexus/new_project

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -c "import nexus; print('✅ NEXUS installed successfully')"
```

## 🧪 **Testing**

### **Run All Tests**
```bash
# Run complete test suite
python -m pytest tests/ -v

# Or use the CI-compatible method
python -c "
import unittest
import sys, os
sys.path.insert(0, os.getcwd())

from tests.core.test_exceptions import TestNexusError
from tests.core.test_logging import TestSetupLogging
from tests.core.config.test_config import TestConfigManager

suite = unittest.TestSuite()
suite.addTest(TestNexusError('test_nexus_error_inheritance'))
suite.addTest(TestNexusError('test_nexus_error_raises'))
suite.addTest(TestSetupLogging('test_setup_logging_basic'))
suite.addTest(TestConfigManager('test_init_default_config_file'))

runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)
"
```

### **Test Coverage Requirements**
- **Minimum Coverage**: 80% (currently 95%+)
- **Critical Paths**: All data pipeline, config management, exception handling
- **CI/CD**: Tests must pass on Python 3.8, 3.9, 3.10, 3.11

## 🔍 **Code Quality**

### **Linting**
```bash
# Run flake8 linter
flake8 nexus/ tests/ --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 nexus/ tests/ --count --exit-zero --max-complexity=10 --max-line-length=88 --statistics

# Fix common issues
black nexus/ tests/
```

### **Type Checking**
```bash
# Run mypy
mypy nexus/ --ignore-missing-imports
```

### **Pre-commit Checks**
```bash
# Run all quality checks before committing
black --check nexus/ tests/
flake8 nexus/ tests/
mypy nexus/ --ignore-missing-imports
python -m pytest tests/ -v
```

## 📁 **Project Structure**

```
nexus/
├── core/
│   ├── config/          # Configuration management
│   ├── data/           # Multi-source data pipeline
│   ├── exceptions.py   # Custom exception classes
│   └── logging.py      # Logging utilities
├── agents/             # AI agent implementations
├── backtesting/        # Backtesting engine
├── monitoring/         # Performance monitoring
├── risk/              # Risk management
└── strategies/        # Trading strategies

tests/                 # Test suite
├── core/             # Core functionality tests
├── integration/      # Integration tests
├── statistical/      # Statistical validation tests
└── conftest.py       # Test configuration

docs/                 # Documentation
├── DEVELOPMENT_GUIDE.md  # This file
├── PHASE1_IMPLEMENTATION.md
└── ROADMAP.md

.github/workflows/    # CI/CD pipelines
├── ci.yml           # Main CI pipeline
└── ...
```

## ⚙️ **Configuration**

### **Environment Variables**
```bash
# Copy and customize
cp .env.example .env

# Edit with your API keys
nano .env
```

### **Required API Keys (Phase 1.1)**
```bash
# Primary data source (Massive.com/Polygon.io)
MASSIVE_API_KEY=your_key_here

# AI analysis (choose one)
DEEPSEEK_KEY=your_deepseek_key
OPENROUTER_API_KEY=your_openrouter_key

# Free supplementary data
COINGECKO_API_KEY=your_coingecko_key
```

### **Optional API Keys (Future Phases)**
```bash
# Trading execution
ALPACA_PAPER_API_KEY=your_alpaca_key
KRAKEN_API_KEY=your_kraken_key

# Additional AI providers
ANTHROPIC_KEY=your_claude_key
OPENAI_KEY=your_openai_key
```

## 🏗️ **Development Workflow**

### **Feature Development**
1. **Create Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Implement Changes**
   - Write tests first (TDD approach)
   - Implement functionality
   - Ensure all tests pass

3. **Code Quality**
   ```bash
   black nexus/ tests/
   flake8 nexus/ tests/
   mypy nexus/ --ignore-missing-imports
   ```

4. **Testing**
   ```bash
   python -m pytest tests/ -v --cov=nexus
   ```

5. **Commit & Push**
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   git push origin feature/your-feature-name
   ```

### **Pull Request Process**
1. **Create PR** with descriptive title and description
2. **CI/CD** must pass all checks
3. **Code Review** required
4. **Merge** only after approval

## 🚨 **Common Issues & Solutions**

### **Import Errors**
```bash
# Symptom: ModuleNotFoundError
# Solution: Install dependencies
pip install -r requirements.txt

# Or activate virtual environment
source venv/bin/activate
```

### **Test Failures**
```bash
# Symptom: Tests failing on CI but passing locally
# Solution: Check Python version compatibility
python --version

# Run tests with verbose output
python -m pytest tests/ -v -s
```

### **API Key Issues**
```bash
# Symptom: External API calls failing
# Solution: Check .env file configuration
cat .env | grep -E "(API_KEY|KEY)="

# Verify API keys are set
python -c "import os; print('Keys configured:', bool(os.getenv('MASSIVE_API_KEY')))"
```

### **CI/CD Pipeline Issues**
```bash
# Symptom: GitHub Actions failing
# Solution: Check workflow syntax
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"

# Test locally first
python -c "import unittest; unittest.main(module='tests', exit=False)"
```

## 📊 **Performance Monitoring**

### **Test Performance**
```bash
# Time individual tests
python -m pytest tests/ --durations=10

# Profile code performance
python -c "
import cProfile
from nexus.core.data import DataManager
cProfile.run('DataManager()')
"
```

### **Memory Usage**
```bash
# Check memory usage during tests
python -m pytest tests/ --mem-usage

# Monitor data pipeline memory
python -c "
import psutil
import os
from nexus.core.data import DataManager

process = psutil.Process(os.getpid())
initial_mem = process.memory_info().rss / 1024 / 1024

manager = DataManager()
final_mem = process.memory_info().rss / 1024 / 1024

print(f'Memory usage: {final_mem - initial_mem:.2f} MB')
"
```

## 🔒 **Security Checklist**

### **Before Committing**
- [ ] No API keys in code (use environment variables)
- [ ] No sensitive data logged
- [ ] `.env` file not committed
- [ ] All secrets properly encrypted

### **Environment Security**
- [ ] Use virtual environments
- [ ] Rotate API keys regularly
- [ ] Use HTTPS for all external calls
- [ ] Implement rate limiting

## 📚 **Documentation Updates**

### **When to Update Docs**
- [ ] New features implemented
- [ ] API changes
- [ ] Configuration changes
- [ ] New dependencies added
- [ ] Security updates

### **Documentation Files**
- `README.md` - Project overview and setup
- `docs/ROADMAP.md` - Development roadmap
- `docs/DEVELOPMENT_GUIDE.md` - This file
- `docs/PHASE1_IMPLEMENTATION.md` - Implementation details

## 🚀 **Deployment**

### **Local Deployment**
```bash
# Ensure all dependencies installed
pip install -r requirements.txt

# Run basic health check
python -c "
from nexus.core.data import DataManager
from nexus.core.config import ConfigManager

print('✅ NEXUS core modules loaded successfully')
manager = DataManager()
config = ConfigManager()
print('✅ Data pipeline and configuration ready')
"
```

### **CI/CD Deployment**
- Automatic on push to `main` branch
- Tests run on Python 3.8, 3.9, 3.10, 3.11
- Code quality checks enforced
- Documentation automatically updated

## 📞 **Support & Troubleshooting**

### **Getting Help**
1. **Check this guide first**
2. **Run diagnostic commands**
3. **Check GitHub Issues**
4. **Review CI/CD logs**

### **Diagnostic Commands**
```bash
# Full system check
python -c "
import sys
print(f'Python: {sys.version}')
try:
    import nexus
    print('✅ NEXUS import successful')
except ImportError as e:
    print(f'❌ NEXUS import failed: {e}')

try:
    from nexus.core.data import DataManager
    print('✅ Data pipeline available')
except ImportError as e:
    print(f'❌ Data pipeline failed: {e}')
"

# Environment check
echo "Virtual environment: $VIRTUAL_ENV"
echo "Python path: $PYTHONPATH"
echo "Working directory: $(pwd)"
```

## 🎯 **Success Metrics**

### **Development Quality**
- ✅ All tests passing on CI/CD
- ✅ Code coverage >80%
- ✅ No linting errors
- ✅ Type checking passes

### **Performance Standards**
- ✅ Test execution <30 seconds
- ✅ Memory usage <100MB during testing
- ✅ No external API calls in test suite

### **Maintainability**
- ✅ Clear documentation
- ✅ Modular architecture
- ✅ Consistent code style
- ✅ Proper error handling

---

## 📝 **Change Log**

- **v1.0.0** - Initial Phase 1.1 implementation
- **CI/CD fixes** - unittest migration, cross-platform compatibility
- **Documentation** - Comprehensive development guide

**Last Updated:** November 2025
**Maintainer:** NEXUS Development Team
