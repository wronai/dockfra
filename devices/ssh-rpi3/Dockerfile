FROM lscr.io/linuxserver/openssh-server:latest

# Install additional tools for deployment
RUN apk add --no-cache \
    bash \
    curl \
    jq \
    rsync \
    openssh-client \
    docker-cli

COPY entrypoint-rpi3.sh /custom-cont-init.d/10-rpi3-setup.sh
RUN chmod +x /custom-cont-init.d/10-rpi3-setup.sh

ENV PUID=1000
ENV PGID=1000
ENV LISTEN_PORT=2222
ENV USER_NAME=deployer
ENV SUDO_ACCESS=true
ENV PASSWORD_ACCESS=false

EXPOSE 2222
