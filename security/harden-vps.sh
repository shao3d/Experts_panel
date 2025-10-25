#!/bin/bash

# ==========================================
# Experts Panel - VPS Security Hardening Script
# ==========================================
# This script applies security hardening to the VPS

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print functions
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script needs to be run as root for security modifications"
        print_info "Please run: sudo $0"
        exit 1
    fi
}

# Create non-root user for deployment
create_deployment_user() {
    print_info "Creating deployment user..."

    if ! id "experts-deploy" &>/dev/null; then
        useradd -m -s /bin/bash experts-deploy
        print_success "Created user: experts-deploy"
    else
        print_info "User experts-deploy already exists"
    fi

    # Add user to docker group
    usermod -aG docker experts-deploy
    print_success "Added experts-deploy to docker group"

    # Create .ssh directory
    mkdir -p /home/experts-deploy/.ssh
    chmod 700 /home/experts-deploy/.ssh
    chown experts-deploy:experts-deploy /home/experts-deploy/.ssh

    print_info "Deployment user ready. Add your SSH key to /home/experts-deploy/.ssh/authorized_keys"
}

# Configure UFW firewall
configure_firewall() {
    print_info "Configuring UFW firewall..."

    # Reset UFW to default state
    ufw --force reset

    # Default policies
    ufw default deny incoming
    ufw default allow outgoing

    # Allow SSH (port 22)
    ufw allow ssh
    print_info "Allowed SSH (port 22)"

    # Allow HTTP and HTTPS
    ufw allow 80/tcp
    ufw allow 443/tcp
    print_info "Allowed HTTP (port 80) and HTTPS (port 443)"

    # Enable UFW
    ufw --force enable
    print_success "UFW firewall configured and enabled"
}

# Install and configure fail2ban
setup_fail2ban() {
    print_info "Setting up fail2ban..."

    # Install fail2ban
    apt-get update
    apt-get install -y fail2ban

    # Create custom fail2ban configuration
    cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3
destemail = root@localhost

[sshd]
enabled = true
port = ssh
logpath = /var/log/auth.log
maxretry = 3
bantime = 3600

[nginx-http-auth]
enabled = true
port = http,https
logpath = /var/log/nginx/error.log

[nginx-limit-req]
enabled = true
port = http,https
logpath = /var/log/nginx/error.log

[nginx-botsearch]
enabled = true
port = http,https
logpath = /var/log/nginx/access.log
maxretry = 2
EOF

    # Restart fail2ban
    systemctl enable fail2ban
    systemctl restart fail2ban

    print_success "Fail2ban configured and started"
}

# Configure automatic security updates
setup_security_updates() {
    print_info "Setting up automatic security updates..."

    # Install unattended-upgrades
    apt-get install -y unattended-upgrades apt-listchanges

    # Configure automatic updates
    cat > /etc/apt/apt.conf.d/50unattended-upgrades << 'EOF'
Unattended-Upgrade::Automatic-Reboot "false";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false";

// Automatically upgrade packages from these origins
Unattended-Upgrade::Origins-Pattern {
      "origin=${distro_id},codename=${distro_codename}";
      "origin=${distro_id},codename=${distro_codename}-security";
      "origin=${distro_id},codename=${distro_codename}-updates";
};
EOF

    # Enable automatic updates
    cat > /etc/apt/apt.conf.d/20auto-upgrades << 'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Download-Upgradeable-Packages "1";
APT::Periodic::AutocleanInterval "7";
APT::Periodic::Unattended-Upgrade "1";
EOF

    print_success "Automatic security updates configured"
}

# Secure SSH configuration
secure_ssh() {
    print_info "Securing SSH configuration..."

    # Backup original SSH config
    cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup

    # Apply SSH security settings
    sed -i 's/#PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
    sed -i 's/#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config
    sed -i 's/#PermitEmptyPasswords no/PermitEmptyPasswords no/' /etc/ssh/sshd_config
    sed -i 's/#MaxAuthTries 6/MaxAuthTries 3/' /etc/ssh/sshd_config
    sed -i 's/#ClientAliveInterval 0/ClientAliveInterval 300/' /etc/ssh/sshd_config
    sed -i 's/#ClientAliveCountMax 3/ClientAliveCountMax 2/' /etc/ssh/sshd_config

    # Restart SSH service
    systemctl restart sshd

    print_success "SSH configuration secured"
    print_warning "SSH password authentication disabled. Ensure you have SSH keys set up!"
}

# Setup log monitoring
setup_log_monitoring() {
    print_info "Setting up log monitoring..."

    # Create logrotate configuration for Docker containers
    cat > /etc/logrotate.d/experts-panel << 'EOF'
/var/lib/docker/containers/*/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    copytruncate
    notifempty
}
EOF

    print_success "Log monitoring configured"
}

# Create security monitoring script
create_security_monitor() {
    print_info "Creating security monitoring script..."

    cat > /usr/local/bin/security-monitor.sh << 'EOF'
#!/bin/bash

# Security monitoring script for Experts Panel
# This script checks for common security issues

LOG_FILE="/var/log/security-monitor.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

# Function to log messages
log_message() {
    echo "[$DATE] $1" >> $LOG_FILE
}

# Check for suspicious login attempts
check_failed_logins() {
    local failed_logins=$(grep "Failed password" /var/log/auth.log | grep "$(date '+%b %d')" | wc -l)
    if [[ $failed_logins -gt 10 ]]; then
        log_message "WARNING: High number of failed login attempts: $failed_logins"
    fi
}

# Check disk usage
check_disk_usage() {
    local disk_usage=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    if [[ $disk_usage -gt 80 ]]; then
        log_message "WARNING: High disk usage: ${disk_usage}%"
    fi
}

# Check memory usage
check_memory_usage() {
    local memory_usage=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
    if [[ $memory_usage -gt 90 ]]; then
        log_message "WARNING: High memory usage: ${memory_usage}%"
    fi
}

# Check Docker container status
check_docker_containers() {
    cd /home/experts-deploy/experts-panel 2>/dev/null || return
    if [[ -f "docker-compose.prod.yml" ]]; then
        local unhealthy_containers=$(docker-compose -f docker-compose.prod.yml ps --filter "status=running" --format "table {{.Names}}\t{{.Status}}" | grep -v "healthy\|NAME" | wc -l)
        if [[ $unhealthy_containers -gt 0 ]]; then
            log_message "WARNING: $unhealthy_containers unhealthy containers"
        fi
    fi
}

# Run all checks
check_failed_logins
check_disk_usage
check_memory_usage
check_docker_containers
EOF

    chmod +x /usr/local/bin/security-monitor.sh

    # Add to cron for hourly monitoring
    echo "0 * * * * /usr/local/bin/security-monitor.sh" | crontab -

    print_success "Security monitoring script created and scheduled"
}

# Generate security summary
generate_security_summary() {
    print_info "Generating security summary..."

    cat > /home/experts-deploy/SECURITY_SUMMARY.md << 'EOF'
# VPS Security Summary

## User Management
- SSH access restricted to key-based authentication
- Root login disabled via SSH
- Deployment user: `experts-deploy` with Docker access

## Firewall Configuration (UFW)
- Default policy: deny all incoming traffic
- Allowed: SSH (22), HTTP (80), HTTPS (443)
- Status: Enabled and active

## Intrusion Prevention (Fail2ban)
- SSH protection enabled (3 failed attempts = 1 hour ban)
- Nginx protection enabled
- HTTP bot protection enabled

## Automatic Updates
- Security packages auto-installed daily
- System packages auto-updated weekly
- Unused dependencies automatically removed

## Log Management
- Docker logs automatically rotated (7 days retention)
- Security monitoring script runs hourly
- Logs stored in: `/var/log/security-monitor.log`

## SSH Security Settings
- Root login: disabled
- Password authentication: disabled
- Max authentication attempts: 3
- Session timeout: 5 minutes idle

## Monitoring
- Disk usage alerts (>80%)
- Memory usage alerts (>90%)
- Failed login attempt monitoring
- Docker container health monitoring

## Recommended Actions
1. Set up SSH keys for all users
2. Monitor security logs regularly
3. Keep backup of SSH keys offline
4. Regularly review fail2ban bans
5. Test security monitoring alerts

## Important Files
- SSH config: `/etc/ssh/sshd_config`
- Firewall: `ufw status`
- Fail2ban: `/etc/fail2ban/jail.local`
- Security logs: `/var/log/security-monitor.log`
EOF

    chown experts-deploy:experts-deploy /home/experts-deploy/SECURITY_SUMMARY.md

    print_success "Security summary created: /home/experts-deploy/SECURITY_SUMMARY.md"
}

# Main hardening function
main() {
    echo ""
    print_info "========================================"
    print_info "VPS Security Hardening"
    print_info "========================================"
    echo ""

    check_root
    create_deployment_user
    configure_firewall
    setup_fail2ban
    setup_security_updates
    secure_ssh
    setup_log_monitoring
    create_security_monitor
    generate_security_summary

    print_success "VPS security hardening completed!"
    echo ""
    print_warning "IMPORTANT SECURITY NOTES:"
    echo "1. Root SSH login has been disabled"
    echo "2. Password authentication has been disabled"
    echo "3. Only SSH key authentication is now allowed"
    echo "4. Make sure you have SSH keys set up before logging out!"
    echo ""
    print_info "Review security summary: /home/experts-deploy/SECURITY_SUMMARY.md"
    print_info "Monitor security logs: /var/log/security-monitor.log"
}

# Handle script arguments
case "${1:-}" in
    "help"|"-h"|"--help")
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  (no args)  Full security hardening"
        echo "  help       Show this help message"
        echo ""
        echo "Note: This script must be run as root"
        echo "      Use: sudo $0"
        exit 0
        ;;
    "")
        main
        ;;
    *)
        print_error "Unknown command: $1"
        print_info "Use '$0 help' for usage information"
        exit 1
        ;;
esac