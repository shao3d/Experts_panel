# Railway Deployment Troubleshooting

**Status:** In Progress  
**Created:** 2025-10-18  
**Updated:** 2025-10-18  

## Overview

Troubleshooting and fixing Railway deployment issues for the Experts Panel application, focusing on missing dependencies and configuration problems.

## Context

### Initial Setup
- Repository: https://github.com/shao3d/Experts_panel.git
- Railway service: https://experts-panel-production.up.railway.app
- Deployment region: europe-west4
- Docker-based deployment using detected Dockerfile

### Issues Encountered
1. **Missing python-multipart dependency** - FastAPI requires this for form data processing
2. **Missing tenacity dependency** - Used for retry logic in map_service.py
3. **Environment variable configuration** - Need to set up Railway variables

## Success Criteria

- [x] Identify and fix missing python-multipart dependency
- [x] Identify and fix missing tenacity dependency
- [x] Update requirements.txt with all necessary dependencies
- [x] Configure Railway environment variables
- [x] Set up Railway PostgreSQL database (changed from SQLite+Volume approach)
- [ ] Create database migration/synchronization mechanism
- [x] Verify successful deployment and health check

## Work Log

### 2025-10-18

#### Completed
- Analyzed Railway deployment logs showing repeated startup failures
- Identified missing `python-multipart` dependency causing RuntimeError
- Added `python-multipart==0.0.12` to requirements.txt
- Committed and pushed fix to trigger new Railway deploy
- Discovered second missing dependency: `tenacity==8.5.0` for retry logic
- Updated requirements.txt with both missing dependencies
- Successfully pushed both fixes to GitHub

#### Decisions
- FastAPI requires python-multipart for form data processing in import endpoints
- tenacity library is essential for retry mechanism in map_service.py
- Both dependencies must be explicitly listed in requirements.txt for Docker builds

#### Discovered
- Railway deployment was failing due to missing dependencies not listed in requirements.txt
- Local development worked because packages were already installed in the environment
- Docker builds clean environments and only install what's in requirements.txt
- Health check was failing because application couldn't start due to missing dependencies

#### Root Cause Analysis
- The issue occurred because dependencies were installed locally but not tracked in requirements.txt
- Common "works on my machine" scenario where local environment has packages not in version control
- Need better dependency management process for future development

#### Next Steps
- [COMPLETED] Monitor Railway deployment after latest dependency fixes
- [COMPLETED] Configure environment variables in Railway dashboard
- [IN PROGRESS] Set up Railway PostgreSQL database (changed from SQLite)
- Create database synchronization mechanism between local and production
- Test full API functionality after successful deployment

### 2025-10-18 (Evening Session)

#### Completed
- Successfully deployed to Railway: https://expertspanel-production.up.railway.app
- Fixed deployment URL (corrected from experts-panel to expertspanel)
- Configured PostgreSQL database on Railway (changed from SQLite approach)
- Set up DATABASE_URL environment variable in Railway dashboard
- Verified health endpoint works: returns `{"status": "connected", "database": "postgresql"}`
- Confirmed API is fully functional at production URL
- Tested query endpoint with multi-expert parallel processing

#### Critical Discoveries
- Railway provides managed PostgreSQL which is more reliable than SQLite+Volume
- DATABASE_URL format: `postgresql://user:pass@host:port/dbname`
- Health check now validates database connection status
- API works correctly with PostgreSQL in production environment

#### Current Issue
- Local database `data/experts.db` file not found - need to locate or recreate data
- Need to migrate schema and data from local SQLite to PostgreSQL
- Direct external connection to Railway PostgreSQL not accessible (timeout)

#### Next Immediate Steps
1. Locate local data files (SQLite DB or Telegram JSON exports)
2. If data exists: Create migration script to PostgreSQL
3. If no data: Start with clean PostgreSQL database
4. Test data import/synchronization process
5. Verify full functionality with production database

## Technical Details

### Dependencies Added
```txt
python-multipart==0.0.12  # Required for FastAPI form data processing
tenacity==8.5.0           # Required for retry logic in map_service.py
```

### Deployment Process
1. Railway detects Dockerfile automatically
2. Builds Docker image with requirements.txt dependencies
3. Runs health check against /health endpoint
4. Fails when application can't start due to missing dependencies

### Production Configuration
- **URL**: https://expertspanel-production.up.railway.app
- **Database**: Railway PostgreSQL (managed service)
- **Environment**: DATABASE_URL configured in Railway dashboard
- **Health Check**: Returns database connection status
- **Status**: ✅ Fully operational

### Error Messages
- `RuntimeError: Form data requires "python-multipart" to be installed`
- `ModuleNotFoundError: No module named 'tenacity'`

## Next Steps

1. **[COMPLETED] Monitor Deployment Status**
   - ✅ Railway dashboard shows successful deploy
   - ✅ Health check passes at https://expertspanel-production.up.railway.app/health

2. **[COMPLETED] Environment Configuration**
   - ✅ DATABASE_URL configured in Railway variables
   - ✅ API endpoints tested and working
   - ⚠️ Need to configure OPENAI_API_KEY for full functionality

3. **[IN PROGRESS] Database Setup**
   - ✅ PostgreSQL database configured on Railway
   - 🔄 Locate local data for migration (SQLite DB or JSON files)
   - ⏳ Create database migration script
   - ⏳ Test data import process

4. **[PENDING] Testing & Validation**
   - Test query endpoint with sample data
   - Verify import endpoints work correctly
   - Test multi-expert processing with real data
   - Validate comment group analysis functionality

5. **[PENDING] Documentation**
   - Document PostgreSQL migration process
   - Create production deployment guide
   - Update CLAUDE.md with Railway configuration

## Critical Discoveries

### PostgreSQL vs SQLite+Volume Decision
- **Initial Plan**: Use Railway Volume with SQLite database
- **Discovery**: Railway provides managed PostgreSQL which is more reliable
- **Benefit**: No need to manage file persistence, automatic backups, better performance
- **Implementation**: Changed DATABASE_URL to use Railway PostgreSQL connection string

### Database URL Configuration
- **Format**: `postgresql://user:pass@host:port/dbname`
- **Source**: Railway automatically provides this in environment variables
- **Usage**: Application automatically detects PostgreSQL vs SQLite
- **Health Check**: Now validates database connection status

### Production URL Correction
- **Initial**: `experts-panel-production.up.railway.app`
- **Actual**: `expertspanel-production.up.railway.app` (without 's')
- **Impact**: API was accessible but at different URL than expected

### Environment Variable Requirements
- **DATABASE_URL**: ✅ Configured and working
- **OPENAI_API_KEY**: ⚠️ Needed for LLM functionality
- **Other variables**: Optional for basic functionality

## Lessons Learned

- Always verify all imports are covered in requirements.txt before deployment
- Use clean virtual environments for testing to catch missing dependencies
- Implement dependency checking in CI/CD pipeline
- Document all required dependencies for future reference
- Railway managed services (PostgreSQL) are preferable to self-managed solutions
- Always verify actual deployment URLs vs expected URLs
- Production deployments need different database strategy than local development