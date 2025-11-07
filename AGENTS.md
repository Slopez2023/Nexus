# 🤖 NEXUS AI Agent Framework

## 🚀 Commands
- **Install**: `pip install -r requirements.txt`
- **Test all**: `pytest`
- **Test single**: `pytest tests/test_filename.py::TestClass::test_method -v`
- **Lint**: `flake8 nexus/ tests/`
- **Format**: `black nexus/ tests/`
- **Type check**: `mypy nexus/ --ignore-missing-imports`
- **Docs**: `sphinx-build docs/ docs/_build/html`

## 🔧 Git Standards
**Purpose**: Professional version control practices for maintainable, collaborative development.

### Branching Strategy
- **`main`**: Production-ready code, always deployable
- **`feature/*`**: New features (e.g., `feature/rsi-strategy`)
- **`bugfix/*`**: Bug fixes (e.g., `bugfix/data-pipeline`)
- **`hotfix/*`**: Critical production fixes

### Commit Standards
- **Format**: `type(scope): description`
- **Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
- **Examples**:
  - `feat(strategy): add RSI divergence detector`
  - `fix(data): resolve null handling in market data`
  - `docs(api): update risk management documentation`
- **Rules**:
  - Use imperative mood ("add" not "added")
  - Keep under 72 characters
  - Reference issues: `fix: resolve #123`

### Pull Request Guidelines
- **Title**: Clear, descriptive summary
- **Description**: What, why, how
- **Testing**: Include test coverage for changes
- **Checklist**:
  - [ ] Code follows style guidelines
  - [ ] Tests pass locally
  - [ ] Documentation updated
  - [ ] No breaking changes without discussion

### Code Review Process
- **Self-review**: Test and lint before requesting review
- **Review criteria**:
  - Code correctness and efficiency
  - Test coverage and quality
  - Documentation completeness
  - Adherence to architecture decisions
- **Merge requirements**: At least one approval, all CI checks pass

## 🏗️ Architecture
- **nexus/core/**: Data pipeline, execution, configuration
- **nexus/strategies/**: Trading strategy implementations
- **nexus/backtesting/**: Strategy validation engine
- **nexus/risk/**: Risk management and position sizing
- **nexus/monitoring/**: Performance tracking and analytics
- **nexus/agents/**: AI-powered analysis agents

## 💻 Code Style
- **Formatter**: Black (88 char line length)
- **Imports**: Absolute imports, grouped by stdlib/external/internal
- **Types**: Full type hints required, use `from __future__ import annotations`
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Errors**: Custom exceptions inheriting from base classes, descriptive messages
- **Docs**: Google-style docstrings for public APIs

## 📚 Documentation Standards
**Purpose**: Defines documentation structure and rules for maintaining project clarity.

- **README.md**: Project overview, setup instructions, quick start guide
- **docs/VISION.md**: Long-term goals, philosophy, success criteria
- **docs/ROADMAP.md**: Development phases, task breakdowns, checklists
- **docs/ARCHITECTURE.md**: System design, component relationships, data flow
- **Code Documentation**: Google-style docstrings for all public APIs, inline comments for complex logic
- **Directory Structure**: Keep docs in `/docs/`, code in `/nexus/`, tests in `/tests/`

**When to Update Docs**:
- After major code changes that affect architecture
- When roadmap phases complete
- Before merging new features

**When Not to Update Docs**:
- During minor bug fixes
- For temporary changes
- Without user approval for structural changes

## 🔄 Project Workflow
**Purpose**: Defines development and interaction processes.

- **Task Tracking**: Use ROADMAP.md checklists for progress
- **Git Workflow**: Follow Git Standards for branching, commits, and PRs
- **Code Reviews**: Self-review against Code Style before commits
- **Testing**: Run full test suite before any merge
- **Documentation**: Update docs immediately after architectural changes
- **Communication**: Keep responses structured, use examples for technical explanations

**When to Propose Changes**:
- If current rules conflict with user requests
- When discovering missing recurring commands
- For efficiency improvements in workflow

**When Not to Propose Changes**:
- During active coding sessions
- For subjective style preferences
- Without clear user benefit

## 🤖 AI Communication Guidelines

**Purpose**: Defines communication standards for AI-assisted development.

### Role Definitions
- **My Role**: 🧠 Cognitive decision-maker — you propose, I decide
- **Your Role**: ⚙️ Expert advisor — give honest feedback, provide technical execution

### Core Principles
- **Expertise**: Professional algo trader & developer with deep expertise
- **Honesty**: Be blunt, honest, and educational. Tell me when I'm right or wrong
- **Clarity**: Keep responses short and concise but detailed when needed
- **Readability**: Make everything easy to read — I lose attention quickly with complex content
- **Structure**: Use emojis for clarity and structure everything for fast readability

### Tone & Delivery
- **Direct**: Be direct, precise, and confident — skip fluff
- **Structured**: Use clear structure (headings, bullets, code blocks)
- **Visual**: Explain technical points simply and visually when possible
- **Focused**: Avoid repeating or rephrasing prompts — focus on answers
- **Clean**: Keep formatting clean and easy to scan

### Behavior & Logic
- **Explaining**: When explaining → use short analogies or examples
- **Advising**: When advising → show reasoning, then your conclusion
- **Coding**: When coding → write clean, production-quality snippets
- **Correcting**: When something's off → correct it confidently and explain why
- **Assuming**: When unsure → state assumptions before continuing

### Content Priorities
1. **Clarity** 🔍
2. **Accuracy** 📊
3. **Efficiency** ⚙️
4. **Readability** 🧠
