FROM alpine:3.19

RUN apk add --no-cache \
    bash \
    openssh-client \
    python3 \
    py3-pip \
    xvfb \
    x11vnc \
    novnc \
    websockify \
    fluxbox \
    xterm \
    curl \
    jq \
    font-noto

WORKDIR /vnc

COPY startup.sh /vnc/startup.sh
RUN chmod +x /vnc/startup.sh

# Setup SSH config for RPi3 connection
RUN mkdir -p /root/.ssh && \
    echo "Host *" > /root/.ssh/config && \
    echo "  StrictHostKeyChecking no" >> /root/.ssh/config && \
    echo "  UserKnownHostsFile /dev/null" >> /root/.ssh/config && \
    chmod 600 /root/.ssh/config

EXPOSE 6080 5900

CMD ["/vnc/startup.sh"]
