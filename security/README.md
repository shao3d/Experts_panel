# Production Security Configuration

This directory contains security hardening scripts and configurations for production deployment.

## Files

- `harden-vps.sh` - Complete VPS security hardening script
- `README.md` - This documentation file

## Security Hardening Script

The `harden-vps.sh` script implements comprehensive security measures:

### User Management
- Creates dedicated `experts-deploy` user
- Disables root SSH access
- Configures SSH key-only authentication
- Adds user to Docker group

### Firewall Configuration (UFW)
- Blocks all incoming traffic by default
- Allows SSH (port 22)
- Allows HTTP (port 80) and HTTPS (port 443)
- Enables and activates firewall

### Intrusion Prevention
- Configures fail2ban for SSH protection
- Sets up nginx HTTP protection
- Implements bot attack prevention
- 3 failed attempts = 1 hour ban

### Automatic Security Updates
- Daily security package installation
- Weekly system updates
- Automatic cleanup of unused dependencies

### SSH Security
- Disables root login
- Disables password authentication
- Limits authentication attempts (3 max)
- Configures session timeout (5 minutes)

### Log Monitoring
- Docker log rotation (7 days retention)
- Hourly security monitoring script
- Disk usage alerts (>80%)
- Memory usage alerts (>90%)
- Failed login monitoring

## Usage

Run the security hardening script:

```bash
sudo ./security/harden-vps.sh
```

## Pre-Deployment Checklist

Before running the security hardening:

1. **SSH Keys Setup**
   - Ensure you have SSH keys configured
   - Test SSH key authentication works
   - Backup SSH keys securely

2. **User Access**
   - Have at least one user with sudo access
   - Test user can run sudo commands

3. **Backup Critical Data**
   - Backup important configuration files
   - Document current SSH settings

## Post-Deployment Security

### SSH Access
```bash
# Use SSH key authentication
ssh -i ~/.ssh/your-key experts-deploy@your-vps-ip

# No more password authentication
# No more root login
```

### Firewall Management
```bash
# Check firewall status
sudo ufw status verbose

# Allow additional ports if needed
sudo ufw allow PORT_NUMBER

# Block IP addresses
sudo ufw deny IP_ADDRESS
```

### Fail2ban Management
```bash
# Check fail2ban status
sudo fail2ban-client status

# Check specific jail
sudo fail2ban-client status sshd

# Unban an IP
sudo fail2ban-client set sshd unbanip IP_ADDRESS
```

### Security Monitoring
```bash
# View security logs
tail -f /var/log/security-monitor.log

# Check fail2ban logs
tail -f /var/log/fail2ban.log

# View SSH authentication logs
tail -f /var/log/auth.log
```

## Security Best Practices

### Regular Maintenance
1. Review security logs weekly
2. Check for suspicious login attempts
3. Monitor system resource usage
4. Update SSH keys periodically

### Backup Strategy
1. Backup SSH keys to secure location
2. Document all security configurations
3. Keep offline backups of critical files
4. Test restore procedures regularly

### Incident Response
1. Have incident response plan ready
2. Document emergency contact procedures
3. Know how to quickly disable services
4. Have backup VPS access method

## Important Security Files

- SSH Configuration: `/etc/ssh/sshd_config`
- Firewall Rules: `ufw status`
- Fail2ban Configuration: `/etc/fail2ban/jail.local`
- Security Monitor: `/usr/local/bin/security-monitor.sh`
- Security Logs: `/var/log/security-monitor.log`

## Warnings

⚠️ **CRITICAL**: After running security hardening:
- Root SSH login will be disabled
- Password authentication will be disabled
- Only SSH key authentication will work
- Make sure you have SSH keys set up before logging out!

## Troubleshooting

### If Locked Out
1. Use VPS provider's console access
2. Re-enable SSH authentication temporarily
3. Check SSH key configuration
4. Verify user permissions

### Common Issues
- SSH key permissions must be 600
- User must be in docker group
- Firewall must allow SSH port
- Fail2ban may block legitimate IPs