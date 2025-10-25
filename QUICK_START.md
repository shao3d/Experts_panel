# Experts Panel - VPS Quick Start Guide

This is a simplified guide for rapid deployment to VPS. For detailed instructions, see [DEPLOYMENT.md](DEPLOYMENT.md).

## Prerequisites

- Ubuntu/Debian VPS with sudo access
- Domain name pointing to VPS IP
- OpenRouter API key
- Latest `experts.db` database file

## Quick Deployment (15 minutes)

### 1. VPS Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y curl wget git docker.io docker-compose-plugin certbot

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Clone repository
git clone https://github.com/your-username/experts-panel.git
cd experts-panel
git checkout feature/docker-deployment-vps
```

### 2. SSL Certificate

```bash
# Generate SSL certificate (replace with your domain)
sudo certbot certonly --standalone -d your-domain.com

# Copy certificates to project
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ./ssl/
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem ./ssl/
sudo chown $USER:$USER ./ssl/*
chmod 600 ./ssl/privkey.pem
chmod 644 ./ssl/fullchain.pem
```

### 3. Configure Environment

```bash
# Copy and edit environment file
cp .env.production.example .env.production
nano .env.production
```

**Required settings:**
```bash
# CRITICAL: Variable name MUST be OPENAI_API_KEY (not OPENROUTER_API_KEY)
# This is correct - system routes OPENAI_API_KEY to OpenRouter API endpoints
OPENAI_API_KEY=sk-your-openrouter-api-key-here
PRODUCTION_ORIGIN=https://your-domain.com
```

### 4. Upload Database

```bash
# Create data directory
mkdir -p data

# Upload your experts.db file (use scp/sftp)
# Example: scp ~/experts.db user@vps-ip:/path/to/experts-panel/data/
```

### 5. Deploy Application

```bash
# Make scripts executable
chmod +x deploy.sh update-ssl.sh

# Run deployment
./deploy.sh
```

### 6. Security Hardening (Optional but Recommended)

```bash
# Apply security hardening
chmod +x security/harden-vps.sh
sudo ./security/harden-vps.sh
```

## Verify Deployment

```bash
# Check status
./deploy.sh status

# Test health endpoint
curl https://your-domain.com/health
```

## Management Commands

```bash
# View logs
./deploy.sh logs

# Restart services
./deploy.sh restart

# Stop services
./deploy.sh stop

# Check SSL certificate
./update-ssl.sh status

# Setup SSL auto-renewal
sudo ./update-ssl.sh setup-auto
```

## Important Notes

⚠️ **Security Warning**: If you run security hardening:
- Root SSH login will be disabled
- Password authentication will be disabled
- Only SSH key authentication will work
- Ensure SSH keys are set up before logging out!

📁 **File Structure**:
```
experts-panel/
├── docker-compose.prod.yml    # Production Docker config
├── .env.production           # Environment variables
├── deploy.sh                 # Deployment script
├── update-ssl.sh            # SSL renewal script
├── data/experts.db          # SQLite database
├── ssl/                     # SSL certificates
├── nginx/nginx-prod.conf   # Nginx configuration
└── security/               # Security hardening
```

🔧 **Troubleshooting**:
- Check logs: `./deploy.sh logs`
- Verify environment: `./deploy.sh check`
- Test certificates: `./update-ssl.sh status`

For complete documentation, see [DEPLOYMENT.md](DEPLOYMENT.md).