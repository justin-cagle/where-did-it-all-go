# Reverse Proxy

## Bundled Caddy (recommended)

By default, WDIAG ships with Caddy as a bundled reverse proxy. Set `DOMAIN_NAME` in your `.env` and it handles everything: TLS certificates via Let's Encrypt, HTTP→HTTPS redirect, security headers, and SSE streaming.

```bash
DOMAIN_NAME=budget.yourdomain.com
CADDY_EMAIL=you@yourdomain.com
COMPOSE_PROFILES=bundled-proxy
```

For a public domain with DNS pointing to your server, Caddy obtains a Let's Encrypt certificate automatically. For `localhost`, Caddy uses a local CA (certificate warning expected and safe to bypass).

## Using your own reverse proxy

If you already have a proxy (Nginx, Traefik, Nginx Proxy Manager), disable Caddy:

```bash
# In .env, remove bundled-proxy from COMPOSE_PROFILES:
COMPOSE_PROFILES=
```

The app then exposes port 8000 directly (HTTP). Your proxy handles TLS and routes to it.

!!! warning "SSE requires no response buffering"
    WDIAG uses Server-Sent Events (SSE) for real-time updates: calendar events, assignment notifications, read-only mode banners. Reverse proxies that buffer responses will break SSE — updates will never reach the browser.

    **You must disable response buffering for the SSE endpoint:** `/api/v1/households/events`

## Nginx

```nginx
server {
    listen 443 ssl;
    server_name budget.yourdomain.com;

    # TLS configuration (your cert paths here)
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # SSE endpoint — disable buffering
    location /api/v1/households/events {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;          # required for SSE
        proxy_cache off;
        proxy_read_timeout 86400s;    # keep SSE connections open
        proxy_http_version 1.1;
    }
}
```

## Traefik

```yaml
# docker-compose.yml labels on the app service
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.wdiag.rule=Host(`budget.yourdomain.com`)"
  - "traefik.http.routers.wdiag.entrypoints=websecure"
  - "traefik.http.routers.wdiag.tls.certresolver=letsencrypt"
  - "traefik.http.services.wdiag.loadbalancer.server.port=8000"
  # SSE streaming — disable buffering
  - "traefik.http.middlewares.wdiag-sse.headers.customresponseheaders.X-Accel-Buffering=no"
```

## Nginx Proxy Manager (NPM)

1. Add a new Proxy Host in NPM.
2. Set **Destination** to `http://your-server-ip:8000`.
3. Enable **Websockets Support** (this also helps SSE).
4. Under **Advanced**, add:
   ```nginx
   location /api/v1/households/events {
       proxy_pass http://your-server-ip:8000;
       proxy_buffering off;
       proxy_cache off;
       proxy_read_timeout 86400s;
   }
   ```
5. Request an SSL certificate (Let's Encrypt).

## External Caddy

If you use your own Caddy instance instead of the bundled one:

```caddyfile
budget.yourdomain.com {
    reverse_proxy localhost:8000

    # SSE — disable buffering
    handle /api/v1/households/events {
        reverse_proxy localhost:8000 {
            flush_interval -1
        }
    }
}
```

Caddy handles SSE correctly by default when `flush_interval -1` is set for the SSE endpoint.
