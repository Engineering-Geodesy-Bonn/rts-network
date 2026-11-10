FROM python:3.13-slim-bookworm
# chronyc queries the clock synchronization state of the host (host networking)
RUN apt-get update && apt-get install -y --no-install-recommends chrony && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .
CMD ["python", "main.py"]
