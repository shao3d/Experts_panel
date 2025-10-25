#!/bin/bash

# ==========================================
# Experts Panel - SSL Certificate Renewal Script
# ==========================================
# This script automates SSL certificate renewal and nginx reload

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

# Check if running as root for certbot operations
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script needs to be run as root for certbot operations"
        print_info "Please run: sudo $0"
        exit 1
    fi
}

# Check dependencies
check_dependencies() {
    print_info "Checking dependencies..."

    local deps=("certbot" "docker" "docker-compose")
    for dep in "${deps[@]}"; do
        if ! command -v $dep &> /dev/null; then
            print_error "$dep is not installed. Please install it first."
            exit 1
        fi
    done

    print_success "All dependencies are installed"
}

# Get domain from environment or ask user
get_domain() {
    if [[ -f ".env.production" ]]; then
        source .env.production
        if [[ -n "$PRODUCTION_ORIGIN" ]]; then
            # Extract domain from URL
            DOMAIN=$(echo "$PRODUCTION_ORIGIN" | sed 's|https://||' | sed 's|/.*||')
            print_info "Found domain in .env.production: $DOMAIN"
        fi
    fi

    if [[ -z "$DOMAIN" ]]; then
        read -p "Enter your domain name (e.g., example.com): " DOMAIN
        if [[ -z "$DOMAIN" ]]; then
            print_error "Domain name is required"
            exit 1
        fi
    fi
}

# Backup current certificates
backup_certificates() {
    print_info "Backing up current certificates..."

    if [[ -d "ssl" ]] && [[ -f "ssl/fullchain.pem" ]]; then
        local backup_dir="ssl/backup-$(date +%Y%m%d-%H%M%S)"
        mkdir -p "$backup_dir"
        cp ssl/*.pem "$backup_dir/" 2>/dev/null || true
        print_success "Certificates backed up to: $backup_dir"
    else
        print_info "No existing certificates to backup"
    fi
}

# Renew SSL certificates
renew_certificates() {
    print_info "Renewing SSL certificates for domain: $DOMAIN"

    # Try renewal first (for existing certificates)
    if certbot certificates 2>/dev/null | grep -q "$DOMAIN"; then
        print_info "Found existing certificate, attempting renewal..."
        if certbot renew --cert-name "$DOMAIN" --quiet; then
            print_success "Certificate renewed successfully"
        else
            print_warning "Renewal failed, attempting to obtain new certificate..."
            obtain_new_certificate
        fi
    else
        print_info "No existing certificate found, obtaining new certificate..."
        obtain_new_certificate
    fi
}

# Obtain new certificate
obtain_new_certificate() {
    print_info "Obtaining new SSL certificate..."

    # Stop nginx to free up port 80
    print_info "Temporarily stopping nginx..."
    docker-compose -f docker-compose.prod.yml stop nginx-reverse-proxy || true

    # Obtain certificate
    if certbot certonly --standalone -d "$DOMAIN" --non-interactive --agree-tos --email admin@"$DOMAIN" --force-renewal; then
        print_success "New certificate obtained successfully"
    else
        print_error "Failed to obtain SSL certificate"
        # Try to restart nginx even if certificate renewal failed
        docker-compose -f docker-compose.prod.yml start nginx-reverse-proxy || true
        exit 1
    fi

    # Restart nginx
    print_info "Restarting nginx..."
    docker-compose -f docker-compose.prod.yml start nginx-reverse-proxy
}

# Copy certificates to project directory
copy_certificates() {
    print_info "Copying certificates to project directory..."

    local cert_path="/etc/letsencrypt/live/$DOMAIN"
    local cert_files=("fullchain.pem" "privkey.pem" "chain.pem")

    # Ensure ssl directory exists
    mkdir -p ssl

    for cert_file in "${cert_files[@]}"; do
        if [[ -f "$cert_path/$cert_file" ]]; then
            cp "$cert_path/$cert_file" "ssl/$cert_file"
            print_info "Copied: $cert_file"
        else
            print_warning "Certificate file not found: $cert_path/$cert_file"
        fi
    done

    # Set proper permissions
    chmod 644 ssl/fullchain.pem ssl/chain.pem
    chmod 600 ssl/privkey.pem
    chown -R $SUDO_USER:$SUDO_USER ssl/

    print_success "Certificates copied with proper permissions"
}

# Reload nginx
reload_nginx() {
    print_info "Reloading nginx configuration..."

    if docker-compose -f docker-compose.prod.yml exec -T nginx-reverse-proxy nginx -t; then
        docker-compose -f docker-compose.prod.yml exec -T nginx-reverse-proxy nginx -s reload
        print_success "Nginx reloaded successfully"
    else
        print_error "Nginx configuration test failed"
        print_info "Restarting nginx container..."
        docker-compose -f docker-compose.prod.yml restart nginx-reverse-proxy
        print_success "Nginx restarted"
    fi
}

# Verify SSL certificate
verify_certificate() {
    print_info "Verifying SSL certificate..."

    # Load domain from .env.production if available
    if [[ -f ".env.production" ]]; then
        source .env.production
        if [[ -n "$PRODUCTION_ORIGIN" ]]; then
            VERIFY_DOMAIN=$(echo "$PRODUCTION_ORIGIN" | sed 's|https://||')
        fi
    fi

    # Use the domain we obtained/renewed for verification
    VERIFY_DOMAIN=${VERIFY_DOMAIN:-$DOMAIN}

    # Check certificate expiry
    if [[ -f "ssl/fullchain.pem" ]]; then
        local expiry_date=$(openssl x509 -in ssl/fullchain.pem -noout -enddate | cut -d= -f2)
        local expiry_timestamp=$(date -d "$expiry_date" +%s)
        local current_timestamp=$(date +%s)
        local days_until_expiry=$(( (expiry_timestamp - current_timestamp) / 86400 ))

        print_info "Certificate expires: $expiry_date ($days_until_expiry days)"

        if [[ $days_until_expiry -gt 30 ]]; then
            print_success "Certificate is valid for more than 30 days"
        elif [[ $days_until_expiry -gt 7 ]]; then
            print_warning "Certificate expires in less than 30 days"
        else
            print_warning "Certificate expires in less than 7 days"
        fi
    fi

    # Test HTTPS connectivity
    print_info "Testing HTTPS connectivity..."
    if curl -s -I "https://$VERIFY_DOMAIN" | grep -q "200 OK\|301 Moved\|302 Found"; then
        print_success "HTTPS is working correctly"
    else
        print_warning "HTTPS test failed - this might be expected if domain doesn't point here yet"
    fi
}

# Setup automatic renewal
setup_auto_renewal() {
    print_info "Setting up automatic certificate renewal..."

    # Create renewal script
    local renewal_script="/usr/local/bin/renew-experts-panel-ssl.sh"
    cat > "$renewal_script" << EOF
#!/bin/bash
# Auto-renewal script for Experts Panel SSL certificates
cd $(pwd)
./update-ssl.sh --auto-renew
EOF

    chmod +x "$renewal_script"

    # Add cron job for daily renewal check (runs at 3:30 AM)
    local cron_entry="30 3 * * * $renewal_script >> /var/log/ssl-renewal.log 2>&1"

    if ! crontab -l 2>/dev/null | grep -q "renew-experts-panel-ssl"; then
        (crontab -l 2>/dev/null; echo "$cron_entry") | crontab -
        print_success "Added daily renewal cron job"
    else
        print_info "Cron job already exists"
    fi
}

# Show certificate status
show_status() {
    print_info "SSL Certificate Status:"
    echo ""

    if [[ -f "ssl/fullchain.pem" ]]; then
        echo "Certificate file: ssl/fullchain.pem"
        echo "Private key file: ssl/privkey.pem"
        echo ""

        local cert_info=$(openssl x509 -in ssl/fullchain.pem -noout -text)
        echo "Subject: $(echo "$cert_info" | grep "Subject:" | sed 's/.*Subject: //')"
        echo "Issuer: $(echo "$cert_info" | grep "Issuer:" | sed 's/.*Issuer: //')"
        echo "Valid from: $(openssl x509 -in ssl/fullchain.pem -noout -startdate | cut -d= -f2)"
        echo "Valid until: $(openssl x509 -in ssl/fullchain.pem -noout -enddate | cut -d= -f2)"
        echo ""

        local expiry_date=$(openssl x509 -in ssl/fullchain.pem -noout -enddate | cut -d= -f2)
        local expiry_timestamp=$(date -d "$expiry_date" +%s)
        local current_timestamp=$(date +%s)
        local days_until_expiry=$(( (expiry_timestamp - current_timestamp) / 86400 ))

        echo "Days until expiry: $days_until_expiry"

        if [[ $days_until_expiry -lt 30 ]]; then
            print_warning "Certificate expires in less than 30 days - renewal recommended"
        else
            print_success "Certificate is valid"
        fi
    else
        print_error "No SSL certificate found in ssl/ directory"
    fi
}

# Main renewal function
main() {
    echo ""
    print_info "========================================"
    print_info "SSL Certificate Renewal"
    print_info "========================================"
    echo ""

    check_root
    check_dependencies
    get_domain
    backup_certificates
    renew_certificates
    copy_certificates
    reload_nginx
    verify_certificate

    print_success "SSL certificate renewal completed!"
    echo ""
    print_info "Certificate status:"
    show_status
}

# Handle script arguments
case "${1:-}" in
    "check"|"status")
        if [[ -f "ssl/fullchain.pem" ]]; then
            show_status
        else
            print_error "No SSL certificate found"
            exit 1
        fi
        ;;
    "setup-auto")
        check_root
        setup_auto_renewal
        print_success "Auto-renewal setup completed"
        ;;
    "--auto-renew")
        # This is used by cron job - only renew if needed
        if [[ -f "ssl/fullchain.pem" ]]; then
            local expiry_date=$(openssl x509 -in ssl/fullchain.pem -noout -enddate | cut -d= -f2)
            local expiry_timestamp=$(date -d "$expiry_date" +%s)
            local current_timestamp=$(date +%s)
            local days_until_expiry=$(( (expiry_timestamp - current_timestamp) / 86400 ))

            if [[ $days_until_expiry -lt 30 ]]; then
                print_info "Certificate expires in $days_until_expiry days - renewing..."
                check_root
                check_dependencies
                get_domain
                backup_certificates
                renew_certificates
                copy_certificates
                reload_nginx
                print_success "Auto-renewal completed"
            else
                print_info "Certificate still valid for $days_until_expiry days - no renewal needed"
            fi
        else
            print_info "No certificate found - skipping auto-renewal"
        fi
        ;;
    "help"|"-h"|"--help")
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  (no args)    Interactive SSL renewal"
        echo "  check        Show certificate status"
        echo "  status       Show certificate status (alias for check)"
        echo "  setup-auto   Setup automatic renewal via cron"
        echo "  --auto-renew Auto-renewal mode (for cron jobs)"
        echo "  help         Show this help message"
        echo ""
        echo "Note: Certificate operations require root privileges"
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