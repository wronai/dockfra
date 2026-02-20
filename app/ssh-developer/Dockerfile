# ssh-developer — extends shared/Dockerfile.ssh-base
FROM dockfra-ssh-base

# Developer-specific extras
RUN apt-get update && apt-get install -y --no-install-recommends \
    htop python3-venv python3-pytest make && \
    pip3 install --break-system-packages flask pytest httpx black flake8 && \
    rm -rf /var/lib/apt/lists/*

# Role user
RUN echo "AllowUsers developer" >> /etc/ssh/sshd_config && \
    useradd -m -s /bin/bash -G sudo developer && \
    echo "developer ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/developer

COPY entrypoint.sh /entrypoint.sh
COPY motd /etc/motd
COPY scripts/ /home/developer/scripts/
RUN chmod +x /entrypoint.sh /home/developer/scripts/*.sh 2>/dev/null; \
    chown -R developer:developer /home/developer
