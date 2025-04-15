FROM python:3.13.1-slim-bookworm
RUN apt-get update && apt-get install -y build-essential 
WORKDIR /app.
COPY . .
RUN pip install .
CMD ["python", "main.py"]