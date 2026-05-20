## Stage 1 — build frontend static files
FROM node:20-alpine AS frontend-builder

WORKDIR /app
RUN npm install -g pnpm

COPY pnpm-lock.yaml pnpm-workspace.yaml package.json ./
COPY apps/frontend/package.json apps/frontend/package.json
RUN pnpm install --frozen-lockfile --filter wdiag-frontend

COPY apps/frontend/ apps/frontend/
WORKDIR /app/apps/frontend

ARG VITE_API_BASE_URL=""
RUN pnpm build


## Stage 2 — AIO image
FROM python:3.12-slim AS aio

RUN apt-get update && apt-get install -y \
    postgresql \
    redis-server \
    supervisor \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Caddy binary
RUN curl -fsSL "https://caddyserver.com/api/download?os=linux&arch=amd64" \
    -o /usr/local/bin/caddy \
    && chmod +x /usr/local/bin/caddy

# uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

COPY apps/backend/pyproject.toml apps/backend/uv.lock* ./
RUN uv sync --no-dev

COPY apps/backend/ .

# Frontend static files
COPY --from=frontend-builder /app/apps/frontend/dist /app/frontend/dist/

# AIO config
COPY deploy/aio/supervisord.conf /etc/supervisor/conf.d/wdiag.conf
COPY deploy/aio/Caddyfile /etc/caddy/Caddyfile
COPY deploy/aio/entrypoint.sh /entrypoint.sh
COPY deploy/aio/pg_hba.conf /etc/postgresql/pg_hba.conf

RUN chmod +x /entrypoint.sh \
    && mkdir -p \
        /var/lib/postgresql/data \
        /var/log/supervisor \
        /data \
    && chown -R postgres:postgres /var/lib/postgresql/

VOLUME ["/var/lib/postgresql/data"]

EXPOSE 80 443

ENTRYPOINT ["/entrypoint.sh"]
