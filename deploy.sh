#!/bin/bash

# ==========================================
# Experts Panel - Production Deployment Script
# ==========================================
# This script automates the deployment of Experts Panel to VPS

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
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root for security reasons"
   exit 1
fi

# Check if required commands exist
check_dependencies() {
    print_info "Checking dependencies..."

    local deps=("docker" "docker-compose" "curl" "wget" "git")
    for dep in "${deps[@]}"; do
        if ! command -v $dep &> /dev/null; then
            print_error "$dep is not installed. Please install it first."
            exit 1
        fi
    done

    print_success "All dependencies are installed"
}

# Check environment variables
check_environment() {
    print_info "Checking environment configuration..."

    if [[ ! -f ".env.production" ]]; then
        print_error ".env.production file not found"
        print_info "Please copy .env.production.example to .env.production and configure it"
        exit 1
    fi

    # Load environment variables
    source .env.production

    # Check required variables
    local required_vars=("OPENAI_API_KEY" "PRODUCTION_ORIGIN")
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var}" ]]; then
            print_error "Required environment variable $var is not set in .env.production"
            exit 1
        fi
    done

    # Check if OPENAI_API_KEY looks valid
    if [[ ! "$OPENAI_API_KEY" =~ ^sk- ]]; then
        print_error "OPENAI_API_KEY appears to be invalid (should start with 'sk-')"
        exit 1
    fi

    # Check if PRODUCTION_ORIGIN uses HTTPS
    if [[ ! "$PRODUCTION_ORIGIN" =~ ^https:// ]]; then
        print_error "PRODUCTION_ORIGIN must use HTTPS (e.g., https://your-domain.com)"
        exit 1
    fi

    print_success "Environment configuration is valid"
}

# Setup directories
setup_directories() {
    print_info "Setting up directories..."

    local dirs=("data" "logs" "ssl" "nginx")
    for dir in "${dirs[@]}"; do
        if [[ ! -d "$dir" ]]; then
            mkdir -p "$dir"
            print_info "Created directory: $dir"
        fi
    done

    # Set proper permissions
    chmod 755 data logs nginx
    chmod 700 ssl

    print_success "Directories are ready"
}

# Check SSL certificates
check_ssl() {
    print_info "Checking SSL certificates..."

    local ssl_files=("ssl/fullchain.pem" "ssl/privkey.pem")

    for ssl_file in "${ssl_files[@]}"; do
        if [[ ! -f "$ssl_file" ]]; then
            print_error "SSL certificate not found: $ssl_file"
            print_info "Please run the following commands to get SSL certificates:"
            print_info "  sudo certbot certonly --standalone -d YOUR_DOMAIN"
            print_info "  sudo cp /etc/letsencrypt/live/YOUR_DOMAIN/fullchain.pem ./ssl/"
            print_info "  sudo cp /etc/letsencrypt/live/YOUR_DOMAIN/privkey.pem ./ssl/"
            print_info "  sudo chown \$USER:$(id -gn) ./ssl/*"
            exit 1
        fi
    done

    # Check certificate permissions
    if [[ $(stat -c %a "ssl/privkey.pem") != "600" ]]; then
        print_warning "Setting proper permissions for private key"
        chmod 600 ssl/privkey.pem
    fi

    if [[ $(stat -c %a "ssl/fullchain.pem") != "644" ]]; then
        chmod 644 ssl/fullchain.pem
    fi

    print_success "SSL certificates are ready"
}

# Check database
check_database() {
    print_info "Checking database..."

    if [[ ! -f "data/experts.db" ]]; then
        print_warning "Database file not found: data/experts.db"
        print_info "Please upload your experts.db file from local development to ./data/"
        print_warning "The application will create a new empty database, but you'll need to import your data"

        # Create empty database
        touch data/experts.db
        print_info "Created empty database file"
    else
        # Check database permissions
        chmod 664 data/experts.db
        print_success "Database file is ready"
    fi
}

# Build and deploy Docker containers
deploy_containers() {
    print_info "Building and deploying Docker containers..."

    # Stop any existing containers
    print_info "Stopping existing containers..."
    docker-compose -f docker-compose.prod.yml down 2>/dev/null || true

    # Build images
    print_info "Building Docker images..."
    docker-compose -f docker-compose.prod.yml build

    # Start containers
    print_info "Starting containers..."
    docker-compose -f docker-compose.prod.yml up -d

    print_success "Containers are deployed"
}

# Wait for services to be healthy
wait_for_health() {
    print_info "Waiting for services to be healthy..."

    local max_attempts=30
    local attempt=1

    while [[ $attempt -le $max_attempts ]]; do
        if curl -f -s http://localhost/health > /dev/null 2>&1; then
            print_success "All services are healthy!"
            break
        fi

        print_info "Attempt $attempt/$max_attempts: Waiting for services..."
        sleep 10
        ((attempt++))
    done

    if [[ $attempt -gt $max_attempts ]]; then
        print_error "Services did not become healthy within expected time"
        print_info "Check logs with: docker-compose -f docker-compose.prod.yml logs"
        exit 1
    fi
}

# Show deployment status
show_status() {
    print_info "Deployment Status:"
    echo ""

    print_info "Container Status:"
    docker-compose -f docker-compose.prod.yml ps

    echo ""
    print_info "Service Health:"
    curl -s http://localhost/health | python3 -m json.tool 2>/dev/null || curl -s http://localhost/health

    echo ""
    print_success "Deployment completed successfully!"
    echo ""
    print_info "Your application should be available at: $PRODUCTION_ORIGIN"
    print_info "Check logs with: docker-compose -f docker-compose.prod.yml logs -f"
    print_info "To stop: docker-compose -f docker-compose.prod.yml down"
}

# Main deployment function
main() {
    echo ""
    print_info "========================================"
    print_info "Experts Panel Production Deployment"
    print_info "========================================"
    echo ""

    check_dependencies
    check_environment
    setup_directories
    check_ssl
    check_database
    deploy_containers
    wait_for_health
    show_status
}

# Handle script arguments
case "${1:-}" in
    "check")
        check_dependencies
        check_environment
        setup_directories
        check_ssl
        check_database
        print_success "All checks passed!"
        ;;
    "stop")
        print_info "Stopping containers..."
        docker-compose -f docker-compose.prod.yml down
        print_success "Containers stopped"
        ;;
    "restart")
        print_info "Restarting containers..."
        docker-compose -f docker-compose.prod.yml restart
        wait_for_health
        print_success "Containers restarted"
        ;;
    "logs")
        docker-compose -f docker-compose.prod.yml logs -f
        ;;
    "status")
        docker-compose -f docker-compose.prod.yml ps
        echo ""
        curl -s http://localhost/health | python3 -m json.tool 2>/dev/null || curl -s http://localhost/health
        ;;
    "help"|"-h"|"--help")
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  (no args)  Full deployment"
        echo "  check      Run pre-deployment checks"
        echo "  stop       Stop all containers"
        echo "  restart    Restart all containers"
        echo "  logs       Show container logs"
        echo "  status     Show deployment status"
        echo "  help       Show this help message"
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