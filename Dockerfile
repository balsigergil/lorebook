# syntax=docker/dockerfile:1

# Front-end assets (Vite: Bloum, htmx, Tailwind, the Tiptap editor island).
FROM node:22-alpine AS assets
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY vite.config.js tsconfig.json ./
COPY assets ./assets
# Tailwind scans the templates for the classes they use.
COPY apps ./apps
RUN npm run build

# Application: Django served over ASGI by Granian.
FROM python:3.14-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
COPY --from=assets /app/dist ./dist
RUN DJANGO_SECRET_KEY=collectstatic python manage.py collectstatic --noinput \
    && useradd --system --uid 1000 --home /app lorebook \
    && mkdir -p /app/uploads \
    && chown lorebook /app/uploads
USER lorebook
EXPOSE 8000
VOLUME ["/app/uploads"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')" || exit 1
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["web"]
