FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
RUN uv sync --frozen --no-dev
EXPOSE 8000
# v2 database: /data/rtsnet.db. On the first start an existing v1 database (/data/database.db)
# is imported automatically; the v1 file itself is never modified.
ENV RTS_DB_PATH=/data/rtsnet.db RTS_LEGACY_DB=/data/database.db
CMD [".venv/bin/rtsapi", "serve", "--host", "0.0.0.0", "--port", "8000"]
