FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY web /app/web
EXPOSE 8050
CMD ["gunicorn", "-b", "0.0.0.0:8050", "web.app:server"]