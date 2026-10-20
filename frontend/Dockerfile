# ==============================================================================
# Multi-Stage Production Dockerfile for DocuMind AI Frontend
# Builds the React + Vite single-page application and serves via Nginx Alpine.
# ==============================================================================

# Stage 1: Build static distribution bundle
FROM node:22-alpine AS builder

WORKDIR /app

# Install dependencies deterministically
COPY package.json package-lock.json ./
RUN npm ci

# Copy frontend source code and compile production assets
COPY . .
# Default build environment uses relative /api/v1 routing through the Nginx reverse proxy
ENV VITE_API_BASE_URL=/api/v1
RUN npm run build

# Stage 2: Hardened Nginx runtime server
FROM nginx:1.27-alpine AS runtime

# Install curl for health checks and openssl for automated fallback TLS generation
RUN apk add --no-cache curl openssl

# Remove default static landing page
RUN rm -rf /usr/share/nginx/html/*

# Copy compiled SPA bundle from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy entrypoint script to ensure SSL certificates exist
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Expose HTTP and HTTPS ports
EXPOSE 80 443

# Health check probe against local HTTPS endpoint
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -k -f https://127.0.0.1/healthz || exit 1

ENTRYPOINT ["/docker-entrypoint.sh"]

# Start Nginx in foreground
CMD ["nginx", "-g", "daemon off;"]
