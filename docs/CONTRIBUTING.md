# 🤝 Contributing to NEXUS

**Guidelines for contributing to the NEXUS AI trading system.**

Thank you for your interest in contributing to NEXUS! We welcome contributions from developers of all skill levels. This document outlines our contribution process and standards.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Pull Request Process](#pull-request-process)
- [Code Standards](#code-standards)
- [Testing](#testing)
- [Documentation](#documentation)
- [Issue Reporting](#issue-reporting)
- [Recognition](#recognition)

## 🤟 Code of Conduct

This project follows a simple code of conduct:

- **Be respectful**: Treat all contributors with respect and kindness
- **Be constructive**: Focus on improving the project, not personal preferences
- **Be patient**: Not everyone is at the same skill level
- **Be collaborative**: Work together to solve problems

## 🚀 Getting Started

### Prerequisites
- Python 3.8+
- Git
- Virtual environment tool (venv, conda, etc.)

### Setup Development Environment

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/yourusername/nexus.git
   cd nexus
   ```

3. **Set up upstream remote**:
   ```bash
   git remote add upstream https://github.com/original-repo/nexus.git
   ```

4. **Create virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

5. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

6. **Set up development tools**:
   ```bash
   # Install pre-commit hooks (if configured)
   pre-commit install

   # Run initial checks
   make check  # or pytest && flake8 nexus/ tests/ && mypy nexus/
   ```

### Choose Your First Contribution

**For beginners:**
- Fix a typo in documentation
- Add a simple unit test
- Improve error messages
- Add type hints to existing code

**For experienced contributors:**
- Implement a new feature from the roadmap
- Fix a bug with comprehensive tests
- Improve performance bottlenecks
- Add new risk management features

## 🔄 Development Workflow

### 1. Choose an Issue
- Check [GitHub Issues](https://github.com/yourusername/nexus/issues) for open tasks
- Look for issues labeled `good first issue` or `help wanted`
- Comment on the issue to indicate you're working on it

### 2. Create a Branch
```bash
# Sync with upstream
git fetch upstream
git checkout main
git merge upstream/main

# Create feature branch
git checkout -b feature/your-feature-name
# or
git checkout -b bugfix/issue-number-description
```

### 3. Make Changes
- Write clean, well-tested code following our [style guidelines](STYLE.md)
- Add tests for new functionality
- Update documentation as needed
- Commit regularly with clear messages

### 4. Test Your Changes
```bash
# Run full test suite
pytest

# Check code quality
flake8 nexus/ tests/
mypy nexus/ --ignore-missing-imports
black --check nexus/ tests/

# Format code if needed
black nexus/ tests/
```

### 5. Update Documentation
- Update docstrings for any API changes
- Add examples for new features
- Update README if needed

### 6. Submit Pull Request
- Push your branch: `git push origin feature/your-feature-name`
- Create PR on GitHub with clear description
- Link to any related issues
- Request review from maintainers

## 📝 Pull Request Process

### PR Requirements
- [ ] **Tests pass**: All CI checks green
- [ ] **Code quality**: Passes linting, type checking, formatting
- [ ] **Documentation**: Updated for any API changes
- [ ] **Self-review**: Checked your own code first
- [ ] **Clear description**: What, why, how

### PR Template
```
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix (non-breaking change)
- [ ] New feature (non-breaking change)
- [ ] Breaking change (fix or feature)
- [ ] Documentation update
- [ ] Code style update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing performed
- [ ] All tests pass locally

## Checklist
- [ ] My code follows the project's style guidelines
- [ ] I have performed a self-review of my code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix/feature works
- [ ] New and existing unit tests pass locally
```

### Review Process
1. **Automated checks**: CI runs tests, linting, type checking
2. **Self-review**: Author reviews their own code
3. **Peer review**: At least one maintainer reviews
4. **Approval**: Reviews approve or request changes
5. **Merge**: Squash merge with descriptive commit message

## 💻 Code Standards

### Python Style
- Follow [PEP 8](https://pep8.org/) with [Black](https://black.readthedocs.io/) formatting
- Use type hints on all public APIs
- Write descriptive docstrings (Google style)
- Keep functions focused and testable

### Commit Messages
Format: `type(scope): description`

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:
```
feat(strategy): add RSI divergence detection
fix(data): resolve null handling in market data
docs(api): update risk management documentation
test(backtest): add performance regression tests
```

### Branch Naming
- Features: `feature/descriptive-name`
- Bug fixes: `bugfix/issue-number-description`
- Hot fixes: `hotfix/critical-issue`

## 🧪 Testing

### Testing Philosophy
- **Test behavior, not implementation**
- **Test public APIs thoroughly**
- **Mock external dependencies**
- **Include edge cases and error conditions**

### Test Structure
```
tests/
├── unit/           # Unit tests (fast, isolated)
├── integration/    # Integration tests (slower, realistic)
└── performance/    # Performance benchmarks
```

### Running Tests
```bash
# All tests
pytest

# With coverage
pytest --cov=nexus --cov-report=html

# Specific test
pytest tests/unit/test_strategy.py::TestSimpleRSI::test_signal_generation -v

# Performance tests
pytest tests/performance/ -k "benchmark"
```

### Test Coverage
- Target: >90% coverage on business logic
- Focus on critical paths and error conditions
- Use coverage reports to identify gaps

## 📚 Documentation

### Documentation Types
- **API Docs**: Auto-generated from docstrings
- **Guides**: User-facing tutorials and explanations
- **Architecture**: System design and decisions
- **Contributing**: This guide and development processes

### Building Documentation
```bash
# Install docs dependencies
pip install sphinx sphinx-rtd-theme

# Build HTML docs
cd docs
make html

# View docs
open _build/html/index.html
```

### Documentation Standards
- Write for users who may not be experts
- Include practical examples
- Keep screenshots/diagrams up to date
- Link related documentation

## 🐛 Issue Reporting

### Bug Reports
**Good bug reports include:**
- Clear title and description
- Steps to reproduce
- Expected vs actual behavior
- Environment details (Python version, OS, etc.)
- Screenshots/logs if applicable
- Minimal code example if possible

**Template:**
```
## Bug Report

**Describe the bug**
A clear description of what the bug is.

**To Reproduce**
Steps to reproduce:
1. Go to '...'
2. Click on '....'
3. See error

**Expected behavior**
A clear description of what you expected to happen.

**Environment**
- Python version: 3.9
- OS: macOS 12.0
- Browser: Chrome 95 (if web-related)

**Additional context**
Add any other context about the problem here.
```

### Feature Requests
**Good feature requests include:**
- Clear problem statement
- Proposed solution
- Alternative solutions considered
- Mockups/diagrams if applicable
- Impact assessment

## 🌟 Recognition

Contributors are recognized through:
- **GitHub contributor stats**
- **Release notes mentions**
- **Maintainer status** for consistent contributors
- **Co-author commits** for collaborative work

### Recognition Levels
- **Contributor**: First merged PR
- **Regular Contributor**: 5+ merged PRs
- **Maintainer**: Consistent high-quality contributions + review privileges

## 📞 Getting Help

- **Questions**: Use [GitHub Discussions](https://github.com/yourusername/nexus/discussions)
- **Issues**: [GitHub Issues](https://github.com/yourusername/nexus/issues)
- **Chat**: [Discord/Slack link if available]

## 📋 Development Checklist

**Before submitting a PR:**
- [ ] Code follows style guidelines
- [ ] Tests pass locally (`pytest`)
- [ ] Code quality checks pass (`make check`)
- [ ] Documentation updated
- [ ] Self-review completed
- [ ] Commit messages clear and descriptive

**For maintainers reviewing:**
- [ ] Code correctness verified
- [ ] Tests adequate and passing
- [ ] Documentation complete
- [ ] No breaking changes without discussion
- [ ] Performance impact assessed

---

*Thank you for contributing to NEXUS! Your efforts help build a more robust and understandable trading system.*
