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

# Install curl for container health checks
RUN apk add --no-cache curl

# Remove default static landing page
RUN rm -rf /usr/share/nginx/html/*

# Copy compiled SPA bundle from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose HTTP port
EXPOSE 80

# Health check
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://127.0.0.1/healthz || exit 1

# Start Nginx in foreground
CMD ["nginx", "-g", "daemon off;"]
