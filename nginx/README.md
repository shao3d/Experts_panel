# Production Nginx Configuration

This directory contains Nginx configuration files for production deployment.

## Files

- `nginx-prod.conf` - Main reverse proxy configuration with SSL termination
- `nginx-ssl.conf` - SSL-specific configuration and security headers

## Configuration Features

- SSL/TLS termination
- HTTP to HTTPS redirect
- Security headers (HSTS, X-Frame-Options, etc.)
- API proxying to backend service
- Static file serving for frontend
- Gzip compression
- Rate limiting
- CORS handling

## Usage

Configuration is mounted in the nginx-reverse-proxy container:

```yaml
volumes:
  - ./nginx/nginx-prod.conf:/etc/nginx/conf.d/default.conf
```

## Testing

After configuration changes:

```bash
# Test nginx configuration
docker-compose exec nginx-reverse-proxy nginx -t

# Reload nginx without downtime
docker-compose exec nginx-reverse-proxy nginx -s reload
```