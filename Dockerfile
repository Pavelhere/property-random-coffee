FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY resources/ ./resources/
COPY src/ ./src/

ENV PYTHONPATH=/app/src
ENV PORT=8080

EXPOSE 8080

CMD gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 60 --chdir /app/src main:app
