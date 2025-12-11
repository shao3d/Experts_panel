# Contributing to Experts Panel

Thank you for your interest in contributing to Experts Panel! This document provides guidelines and information for contributors.

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Google AI Studio API key — get from https://aistudio.google.com/app/apikey
- Git

### Development Setup
```bash
# Clone the repository
git clone https://github.com/shao3d/Experts_panel.git
cd Experts_panel

# Backend setup
cd backend
pip install -r requirements.txt
cp .env.example .env
# Add your GOOGLE_AI_STUDIO_API_KEY to .env

# Frontend setup
cd ../frontend
npm install

# Start development servers
cd ../backend && python3 -m uvicorn src.api.main:app --reload --port 8000
cd ../frontend && npm run dev
```

## 📋 How to Contribute

### Reporting Bugs
- Use the [Bug Report template](.github/ISSUE_TEMPLATE/bug_report.md)
- Provide detailed reproduction steps
- Include system information and logs
- Add screenshots if applicable

### Suggesting Features
- Use the [Feature Request template](.github/ISSUE_TEMPLATE/feature_request.md)
- Describe the use case and expected behavior
- Explain why this feature would be valuable

### Code Contributions
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests if applicable
5. Ensure all tests pass
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## 🏗️ Project Structure

```
Experts_panel/
├── backend/                 # Python FastAPI backend
│   ├── src/
│   │   ├── api/            # API endpoints
│   │   ├── models/         # Database models
│   │   ├── services/       # Business logic
│   │   └── utils/          # Utility functions
│   ├── prompts/            # LLM prompts
│   └── migrations/         # Database migrations
├── frontend/               # React TypeScript frontend
│   └── src/
│       ├── components/     # React components
│       ├── services/       # API client
│       └── types/          # TypeScript interfaces
├── docs/                   # Additional documentation
├── data/                   # Data files
└── tests/                  # Test files
```

## 📝 Coding Standards

### Python (Backend)
- Use type hints for all functions
- Follow PEP 8 style guidelines
- Use async/await for I/O operations
- Write comprehensive docstrings
- Keep functions small and focused

### TypeScript (Frontend)
- Use strict TypeScript mode
- Prefer interfaces over types
- Use functional components with hooks
- Follow React best practices
- Include proper error handling

## 🧪 Testing

### Running Tests
```bash
# Backend tests
cd backend && python -m pytest

# Frontend tests
cd frontend && npm test

# Integration tests
npm run test:e2e
```

### Writing Tests
- Write unit tests for new functions
- Include integration tests for API endpoints
- Test error conditions and edge cases
- Aim for >80% code coverage

## 📋 Pull Request Process

### Before Submitting
- [ ] Code follows project style guidelines
- [ ] Self-review of changes
- [ ] Code builds cleanly without errors
- [ ] All tests pass
- [ ] Documentation is updated if needed

### PR Template
Use the [Pull Request Template](.github/PULL_REQUEST_TEMPLATE.md) and include:
- Clear description of changes
- Testing performed
- Screenshots if UI changes
- Related issues

## 🔧 Development Guidelines

### Git Workflow
- Use descriptive commit messages
- Keep commits atomic and focused
- squash related commits before PR
- Follow conventional commit format

### Database Changes
- Create migration scripts for schema changes
- Test migrations on clean database
- Include rollback scripts if needed

### API Changes
- Update API documentation
- Add versioning for breaking changes
- Include examples in documentation

## 🚨 Code Review Process

### Review Criteria
- Code quality and style
- Performance implications
- Security considerations
- Test coverage
- Documentation completeness

### Review Guidelines
- Be constructive and respectful
- Explain reasoning for suggestions
- Focus on the code, not the author
- Respond to feedback promptly

## 🏆 Recognition

Contributors are recognized in:
- AUTHORS.md file
- Release notes
- Project documentation

## 📞 Getting Help

- 📖 Read the [documentation](docs/)
- 🐛 [Report issues](https://github.com/shao3d/Experts_panel/issues)
- 💬 Start a [discussion](https://github.com/shao3d/Experts_panel/discussions)
- 📧 Contact maintainers

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to Experts Panel! 🎉