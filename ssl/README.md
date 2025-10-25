# SSL Certificates

This directory contains SSL certificates for HTTPS setup using Let's Encrypt.

## Required Files

After SSL setup with certbot, this directory should contain:

- `fullchain.pem` - SSL certificate chain
- `privkey.pem` - Private key for the certificate
- `chain.pem` - Intermediate certificate chain

## Setup Process

1. Install certbot on VPS
2. Generate certificates:
   ```bash
   sudo certbot certonly --standalone -d your-domain.com
   sudo cp /etc/letsencrypt/live/your-domain.com/* ./ssl/
   ```
3. Set proper permissions:
   ```bash
   chmod 600 ./ssl/privkey.pem
   chmod 644 ./ssl/fullchain.pem
   ```

## Renewal

Use the `update-ssl.sh` script to automate certificate renewal:

```bash
./update-ssl.sh
```

## Security

- Private keys should have restrictive permissions (600)
- Certificates should be readable by nginx user (644)
- Never commit certificates to version control