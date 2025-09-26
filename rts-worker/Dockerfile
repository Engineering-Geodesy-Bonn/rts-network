FROM ghcr.io/astral-sh/uv:python3.13-bookworm
COPY . .
RUN uv sync
CMD ["uv", "run", "main.py"]