FROM nginx:alpine

ARG APP_NAME=InfraDemo
ARG APP_VERSION=1.0.0

RUN apk add --no-cache curl

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY public/ /usr/share/nginx/html/

RUN sed -i "s/{{APP_NAME}}/${APP_NAME}/g" /usr/share/nginx/html/index.html && \
    sed -i "s/{{APP_VERSION}}/${APP_VERSION}/g" /usr/share/nginx/html/index.html

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost/health || exit 1
