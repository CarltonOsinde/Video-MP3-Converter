FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py auth_client.py storage.py ./

RUN useradd --create-home appuser
USER appuser

EXPOSE 8080
# Sync workers: each process holds its own RabbitMQ connection (pika's BlockingConnection is not thread-safe).
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "120", "server:server"]
