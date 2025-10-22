# GitHub Actions Workflows

This directory contains GitHub Actions workflows for the Experts Panel project.

## 📋 Available Workflows

### 1. **CI/CD Pipeline** (`.github/workflows/ci.yml`)

**Triggers:**
- Push to `main` or `develop` branches
- Pull requests to `main`

**What it does:**
- ✅ **Backend Validation**: Python syntax, imports, database models
- ✅ **Docker Validation**: Build and test Docker images for backend/frontend
- ✅ **Docker Compose**: Validate and test multi-service setup
- ✅ **Frontend Validation**: TypeScript compilation, build process
- ✅ **Security Checks**: Scan for exposed API keys, validate .gitignore
- ✅ **Configuration Checks**: Verify all required config files exist

**Jobs:**
- `backend-tests` - Python code quality and imports
- `docker-tests` - Docker image builds
- `compose-test` - Docker Compose validation
- `frontend-tests` - Frontend build and TypeScript
- `security-checks` - Security and file validation
- `summary` - Overall CI status report

### 2. **Deploy to Railway** (`.github/workflows/deploy.yml`)

**Triggers:**
- Push to `main` branch
- Manual workflow dispatch

**What it does:**
- 🚀 **Automatic Deployment**: Deploys to Railway when main is updated
- 🔍 **Health Checks**: Waits for deployment and performs health checks
- 📊 **Deployment Summary**: Provides deployment URL and status

**Required Secrets:**
- `RAILWAY_TOKEN` - Railway API token
- `RAILWAY_SERVICE_ID` - (Optional) Railway service ID

## 🚀 Quick Start

1. **CI will run automatically** on any push/PR
2. **Check the Actions tab** in GitHub for results
3. **For deployment**, set up Railway secrets in GitHub repo settings

## 🔧 Configuration

### Required Repository Secrets:

For Railway deployment (optional):
```
RAILWAY_TOKEN=your_railway_api_token
RAILWAY_SERVICE_ID=experts-panel-service-id
```

### Environment Variables:

The CI automatically creates test environment variables, but for production deployment ensure these are set in Railway:
```
OPENAI_API_KEY=your_openai_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
TELEGRAM_API_ID=your_telegram_api_id
TELEGRAM_API_HASH=your_telegram_api_hash
TELEGRAM_CHANNEL=your_telegram_channel
```

## 📊 CI Status Badge

Add this to your README.md:

```markdown
![CI/CD](https://github.com/shao3d/Experts_panel/workflows/CI/CD%20Pipeline/badge.svg)
```

## 🛠️ Local Testing

To test workflows locally:

1. Install act (local GitHub Actions runner):
```bash
brew install act
```

2. Run workflow locally:
```bash
act -j backend-tests
```

## 🐛 Troubleshooting

### Common Issues:

1. **Docker build fails**: Check Dockerfile syntax and dependencies
2. **Python imports fail**: Verify requirements.txt and Python path
3. **Frontend build fails**: Check package.json and TypeScript configuration
4. **Deployment fails**: Verify Railway secrets and environment variables

### Debugging:

- Check individual job logs in GitHub Actions
- Look at the "Summary" step for overall status
- Use `act` for local testing and debugging

## 📝 Notes

- CI runs on every push to main/develop and PR to main
- Deploy workflow only runs on main branch pushes
- All jobs use Ubuntu latest runners
- Docker layer caching is enabled for faster builds
- Security checks prevent committing sensitive data

## 🔄 Workflow Status

Current status can be checked in the "Actions" tab of the GitHub repository.