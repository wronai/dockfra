FROM python:3.11-slim

ARG APP_VERSION=1.0.0
ENV APP_VERSION=${APP_VERSION}
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/data

EXPOSE 8082

CMD ["gunicorn", "--bind", "0.0.0.0:8082", "--workers", "2", "--timeout", "120", "app:app"]
