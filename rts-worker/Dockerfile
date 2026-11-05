FROM python:3.13.1-slim-bookworm
# chrony provides chronyc, which queries the clock synchronization state of the host (host networking)
RUN apt-get update && apt-get install -y --no-install-recommends build-essential chrony && rm -rf /var/lib/apt/lists/*
WORKDIR /app.
COPY . .
RUN pip install .
CMD ["python", "main.py"]