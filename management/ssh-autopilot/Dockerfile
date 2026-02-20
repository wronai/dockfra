# ssh-autopilot — extends shared/Dockerfile.ssh-base
FROM dockfra-ssh-base

# Role user
RUN echo "AllowUsers autopilot" >> /etc/ssh/sshd_config && \
    useradd -m -s /bin/bash -G sudo autopilot && \
    echo "autopilot ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/autopilot

COPY entrypoint.sh /entrypoint.sh
COPY motd /etc/motd
COPY scripts/ /home/autopilot/scripts/
COPY autopilot-daemon.sh /home/autopilot/autopilot-daemon.sh
RUN chmod +x /entrypoint.sh /home/autopilot/scripts/*.sh /home/autopilot/autopilot-daemon.sh 2>/dev/null; \
    chown -R autopilot:autopilot /home/autopilot
