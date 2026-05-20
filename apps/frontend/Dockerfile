FROM node:22-alpine AS builder
WORKDIR /app

RUN npm install -g pnpm@10

COPY pnpm-lock.yaml pnpm-workspace.yaml package.json ./
COPY apps/frontend/package.json apps/frontend/package.json
RUN pnpm install --frozen-lockfile --filter wdiag-frontend

COPY apps/frontend/ apps/frontend/
WORKDIR /app/apps/frontend

ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN pnpm build

FROM nginx:alpine AS serve
COPY --from=builder /app/apps/frontend/dist /usr/share/nginx/html
COPY apps/frontend/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
