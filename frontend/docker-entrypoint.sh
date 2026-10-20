#!/bin/sh
set -e

# Ensure SSL directory exists
mkdir -p /etc/nginx/ssl

# If certificates do not exist, generate automatic self-signed fallback certificates
if [ ! -f /etc/nginx/ssl/cert.pem ] || [ ! -f /etc/nginx/ssl/key.pem ]; then
    echo "[DocuMind Nginx] No custom SSL certificate mounted in /etc/nginx/ssl."
    echo "[DocuMind Nginx] Generating automatic 2048-bit self-signed SSL certificate for HTTPS..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout /etc/nginx/ssl/key.pem \
        -out /etc/nginx/ssl/cert.pem \
        -subj "/C=US/ST=State/L=City/O=DocuMind/OU=AI/CN=localhost" \
        2>/dev/null
    echo "[DocuMind Nginx] Self-signed certificate ready at /etc/nginx/ssl/cert.pem."
fi

# Execute CMD passed to container (typically: nginx -g "daemon off;")
exec "$@"
