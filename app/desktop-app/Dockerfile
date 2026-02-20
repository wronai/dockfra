FROM python:3.11-slim

ARG APP_NAME=InfraDemo
ARG APP_VERSION=1.0.0
ENV APP_NAME=${APP_NAME}
ENV APP_VERSION=${APP_VERSION}
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl xvfb && \
    rm -rf /var/lib/apt/lists/*

# Create dist and output dirs
RUN mkdir -p /app/dist /app/src /output/frontend/downloads

COPY src/ /app/src/
COPY server.py /app/server.py
COPY build.sh /app/build.sh

RUN chmod +x /app/build.sh

EXPOSE 8083

# Start Xvfb + build + serve
CMD ["/bin/bash", "-c", "Xvfb :99 -screen 0 1280x720x24 & export DISPLAY=:99 && /app/build.sh && python /app/server.py"]
