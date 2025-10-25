# Experts Panel - Production Deployment Guide

This guide provides step-by-step instructions for deploying Experts Panel to a Virtual Private Server (VPS) with Docker, SSL/HTTPS, and security hardening.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [VPS Preparation](#vps-preparation)
3. [Domain and DNS Setup](#domain-and-dns-setup)
4. [SSL Certificate Setup](#ssl-certificate-setup)
5. [Application Deployment](#application-deployment)
6. [Security Hardening](#security-hardening)
7. [Monitoring and Maintenance](#monitoring-and-maintenance)
8. [Troubleshooting](#troubleshooting)
9. [Backup and Recovery](#backup-and-recovery)

## Prerequisites

### Required Software on VPS
- Ubuntu 20.04+ or Debian 10+ (recommended)
- Docker and Docker Compose
- Git
-curl and wget
- sudo access

### Local Development Setup
- Git clone of the experts-panel repository
- Latest `experts.db` database file
- OpenRouter API key

### Domain Requirements
- Registered domain name
- Ability to modify DNS records
- Domain pointing to VPS IP address

## VPS Preparation

### 1. Update System Packages

```bash
# Update package lists
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y curl wget git docker.io docker-compose-plugin certbot

# Add current user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

### 2. Clone Repository

```bash
# Clone the repository
git clone https://github.com/your-username/experts-panel.git
cd experts-panel

# Checkout the production branch
git checkout feature/docker-deployment-vps
```

### 3. Create Deployment User

```bash
# Create deployment user (optional but recommended)
sudo adduser --disabled-password --gecos '' experts-deploy
sudo usermod -aG docker experts-deploy
sudo usermod -aG sudo experts-deploy

# Switch to deployment user
sudo su - experts-deploy
cd /home/experts-deploy/experts-panel
```

## Domain and DNS Setup

### 1. Configure DNS Records

Add the following DNS records for your domain:

```
Type    Name            Value           TTL
A       @               VPS_IP_ADDRESS  300
A       www             VPS_IP_ADDRESS  300
AAAA    @               IPV6_ADDRESS    300 (optional)
AAAA    www             IPV6_ADDRESS    300 (optional)
```

### 2. Verify DNS Propagation

```bash
# Check DNS resolution
nslookup your-domain.com
nslookup www.your-domain.com

# Should return your VPS IP address
```

## SSL Certificate Setup

### 1. Install Let's Encrypt Certbot

```bash
# Install certbot (Ubuntu/Debian)
sudo apt install certbot

# Or using snap (recommended)
sudo snap install certbot --classic
```

### 2. Generate SSL Certificate

```bash
# Stop any existing web services on port 80
sudo systemctl stop nginx apache2 2>/dev/null || true

# Generate certificate
sudo certbot certonly --standalone -d your-domain.com -d www.your-domain.com

# Copy certificates to project directory
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ./ssl/
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem ./ssl/
sudo cp /etc/letsencrypt/live/your-domain.com/chain.pem ./ssl/

# Set proper permissions
sudo chown $USER:$USER ./ssl/*
chmod 600 ./ssl/privkey.pem
chmod 644 ./ssl/fullchain.pem ./ssl/chain.pem
```

### 3. Setup Auto-Renewal

```bash
# Setup automatic renewal
./update-ssl.sh setup-auto

# Test renewal process
sudo ./update-ssl.sh --auto-renew
```

## Application Deployment

### 1. Configure Environment Variables

```bash
# Copy environment template
cp .env.production.example .env.production

# Edit environment file
nano .env.production
```

**Required configuration in `.env.production`:**

```bash
# Critical: OpenRouter API key
# IMPORTANT: Variable name MUST be OPENAI_API_KEY (not OPENROUTER_API_KEY)
# This is correct - system routes OPENAI_API_KEY to OpenRouter API endpoints
OPENAI_API_KEY=sk-your-openrouter-api-key-here

# Production domain (must match SSL certificate)
PRODUCTION_ORIGIN=https://your-domain.com

# Database path (keep default)
DATABASE_URL=sqlite:///data/experts.db

# Production settings
ENVIRONMENT=production
LOG_LEVEL=INFO
```

### 2. Upload Database File

```bash
# Upload your latest experts.db from local development
# Use scp, sftp, or any file transfer method

# Example using scp from your local machine:
scp ~/path/to/experts.db user@vps-ip:/home/user/experts-panel/data/

# Set proper permissions
chmod 664 data/experts.db
```

### 3. Run Deployment

```bash
# Make script executable (if not already)
chmod +x deploy.sh

# Run pre-deployment checks
./deploy.sh check

# Deploy the application
./deploy.sh
```

The deployment script will:
- Check all dependencies
- Verify environment configuration
- Build Docker images
- Start all services
- Wait for health checks
- Show deployment status

### 4. Verify Deployment

```bash
# Check service status
./deploy.sh status

# Test application
curl https://your-domain.com/health

# Should return:
# {"status":"healthy","database":"healthy","openai_configured":true,"timestamp":1234567890}
```

## Security Hardening

### 1. Run Security Hardening Script

```bash
# Make security script executable
chmod +x security/harden-vps.sh

# Run security hardening (requires sudo)
sudo ./security/harden-vps.sh
```

The security script will:
- Create dedicated deployment user
- Configure UFW firewall
- Setup fail2ban intrusion prevention
- Configure automatic security updates
- Secure SSH configuration
- Setup log monitoring

### 2. SSH Security Configuration

After security hardening:
- Root SSH login is disabled
- Password authentication is disabled
- Only SSH key authentication works

**Ensure you have SSH keys configured before logging out!**

### 3. Review Security Settings

```bash
# Check firewall status
sudo ufw status verbose

# Check fail2ban status
sudo fail2ban-client status

# Review security summary
cat /home/experts-deploy/SECURITY_SUMMARY.md
```

## Monitoring and Maintenance

### 1. Application Monitoring

```bash
# View container status
docker-compose -f docker-compose.prod.yml ps

# View application logs
./deploy.sh logs

# Check health endpoint
curl https://your-domain.com/health
```

### 2. SSL Certificate Monitoring

```bash
# Check certificate status
./update-ssl.sh status

# View certificate expiry
openssl x509 -in ssl/fullchain.pem -noout -enddate

# Monitor auto-renewal logs
tail -f /var/log/ssl-renewal.log
```

### 3. Security Monitoring

```bash
# View security logs
tail -f /var/log/security-monitor.log

# Check failed login attempts
sudo grep "Failed password" /var/log/auth.log

# Monitor fail2ban bans
sudo fail2ban-client status sshd
```

### 4. System Resource Monitoring

```bash
# Check disk usage
df -h

# Check memory usage
free -h

# Check Docker resource usage
docker stats
```

## Troubleshooting

### Common Issues

#### 1. SSL Certificate Problems

```bash
# Certificate not found error
# Solution: Ensure certificates are in ssl/ directory
ls -la ssl/

# Permission denied on certificates
# Solution: Set correct permissions
chmod 600 ssl/privkey.pem
chmod 644 ssl/fullchain.pem

# Certificate expired
# Solution: Renew certificates
sudo ./update-ssl.sh
```

#### 2. Container Startup Issues

```bash
# Containers not starting
# Check logs:
./deploy.sh logs

# Database permission issues
# Fix permissions:
sudo chown -R 1000:1000 data/
chmod 664 data/experts.db

# Port conflicts
# Check what's using ports:
sudo netstat -tulpn | grep :80
sudo netstat -tulpn | grep :443
```

#### 3. Health Check Failures

```bash
# Health check failing
# Check backend health:
docker-compose exec backend-api curl -f http://localhost:8000/health

# Check API key configuration
docker-compose exec backend-api env | grep OPENAI_API_KEY

# Check database connectivity
docker-compose exec backend-api sqlite3 data/experts.db ".tables"
```

#### 4. Performance Issues

```bash
# High memory usage
# Check container limits:
docker-compose -f docker-compose.prod.yml config

# High CPU usage
# Check resource usage:
docker stats

# Slow response times
# Check nginx logs:
docker-compose logs nginx-reverse-proxy
```

### Debug Commands

```bash
# Full system status
./deploy.sh status

# Container logs with details
docker-compose -f docker-compose.prod.yml logs --tail=100

# Network connectivity test
docker network ls
docker network inspect experts-panel_experts-panel-network

# SSL certificate verification
openssl s_client -connect your-domain.com:443 -servername your-domain.com
```

## Backup and Recovery

### Database Backup Strategy

Since you're using the MacBook + Dropbox + GitHub approach:

```bash
# To update production database from local:
# 1. Stop containers
./deploy.sh stop

# 2. Replace database file
cp ~/Downloads/fresh-experts.db ./data/experts.db

# 3. Restart containers
./deploy.sh restart

# To create local backup from production:
# 1. Copy database from VPS
scp user@vps-ip:/home/user/experts-panel/data/experts.db ~/Downloads/

# 2. Sync to Dropbox and commit to GitHub
```

### Configuration Backup

```bash
# Backup all configuration files
tar -czf config-backup-$(date +%Y%m%d).tar.gz \
    .env.production \
    nginx/nginx-prod.conf \
    ssl/ \
    docker-compose.prod.yml \
    deploy.sh \
    update-ssl.sh
```

### Disaster Recovery

```bash
# Complete recovery procedure:
# 1. Clone repository on new VPS
git clone https://github.com/your-username/experts-panel.git
cd experts-panel
git checkout feature/docker-deployment-vps

# 2. Setup environment
cp .env.production.example .env.production
# Edit .env.production with your values

# 3. Upload database
scp user@backup:/path/to/experts.db ./data/

# 4. Setup SSL certificates
# Follow SSL setup instructions above

# 5. Deploy application
./deploy.sh

# 6. Apply security hardening
sudo ./security/harden-vps.sh
```

## Maintenance Schedule

### Daily (Automated)
- SSL certificate renewal check
- Security monitoring scan
- Log rotation

### Weekly
- Review security logs
- Check disk space usage
- Monitor application performance
- Update system packages

### Monthly
- Review and update SSL certificates
- Backup configuration files
- Security audit of access logs
- Performance optimization review

### Quarterly
- Major system updates
- Security configuration review
- Disaster recovery testing
- Documentation updates

## Support and Resources

### Documentation Files
- `nginx/nginx-prod.conf` - Nginx configuration
- `security/README.md` - Security documentation
- `.env.production.example` - Environment template

### Useful Commands
- `./deploy.sh help` - Deployment script help
- `./update-ssl.sh help` - SSL script help
- `docker-compose -f docker-compose.prod.yml --help` - Docker help

### Log Locations
- Application logs: `./deploy.sh logs`
- Security logs: `/var/log/security-monitor.log`
- Nginx logs: `docker-compose logs nginx-reverse-proxy`
- SSL renewal logs: `/var/log/ssl-renewal.log`

## Contact and Support

For issues with this deployment:
1. Check troubleshooting section above
2. Review log files for error messages
3. Test each component individually
4. Consult the GitHub repository for latest updates

---

**Important Notes:**
- Always backup before making changes
- Test in staging environment first
- Monitor security logs regularly
- Keep SSH keys secure and backed up
- Never commit sensitive data to version control