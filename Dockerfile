# Stage 1: Build React frontend
FROM node:20-slim AS client-builder
WORKDIR /build
COPY client/package.json client/package-lock.json ./
RUN npm ci --legacy-peer-deps
COPY client/ .
RUN npm run build

# Stage 2: Build Python environment with uv
FROM python:3.11-slim AS python-builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy
ENV UV_COMPILE_BYTECODE=1
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-install-project --no-dev
COPY relay/ relay/
COPY tunnel/ tunnel/
RUN uv sync --locked --no-editable --no-dev

# Stage 3: Slim runtime
FROM python:3.11-slim
WORKDIR /app
COPY --from=python-builder /app/.venv /app/.venv
COPY --from=client-builder /build/dist /app/client/dist
COPY relay/templates /app/relay/templates
ENV PATH="/app/.venv/bin:$PATH"
ENV VIRTUAL_ENV="/app/.venv"
ENV PORT=8080
CMD ["python", "-m", "relay.cli"]
