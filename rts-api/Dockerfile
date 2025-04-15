FROM ghcr.io/astral-sh/uv:python3.13-bookworm
COPY . .
RUN uv sync
EXPOSE 8000
CMD ["uv", "run", "rtsapi"]