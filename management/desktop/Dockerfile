FROM alpine:3.19

RUN apk add --no-cache \
    bash curl \
    xvfb x11vnc novnc websockify fluxbox xterm \
    chromium font-noto \
    openssh-client jq python3

WORKDIR /desktop
COPY startup.sh /desktop/startup.sh
RUN chmod +x /desktop/startup.sh

RUN mkdir -p /root/.ssh && \
    echo "Host *\n  StrictHostKeyChecking no\n  UserKnownHostsFile /dev/null" > /root/.ssh/config && \
    chmod 600 /root/.ssh/config

EXPOSE 6081 5901
CMD ["/desktop/startup.sh"]
