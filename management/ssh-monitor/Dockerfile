# ssh-monitor — extends shared/Dockerfile.ssh-base
FROM dockfra-ssh-base

# Monitor-specific extras
RUN apt-get update && apt-get install -y --no-install-recommends htop iproute2 && \
    rm -rf /var/lib/apt/lists/*

# Role user
RUN echo "AllowUsers monitor" >> /etc/ssh/sshd_config && \
    useradd -m -s /bin/bash -G sudo monitor && \
    echo "monitor ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/monitor

COPY entrypoint.sh /entrypoint.sh
COPY motd /etc/motd
COPY scripts/ /home/monitor/scripts/
COPY monitor-daemon.sh /home/monitor/monitor-daemon.sh
RUN chmod +x /entrypoint.sh /home/monitor/scripts/*.sh /home/monitor/monitor-daemon.sh 2>/dev/null; \
    chown -R monitor:monitor /home/monitor
