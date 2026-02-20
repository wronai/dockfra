# ssh-manager — extends shared/Dockerfile.ssh-base
FROM dockfra-ssh-base

# Role user
RUN echo "AllowUsers manager" >> /etc/ssh/sshd_config && \
    useradd -m -s /bin/bash -G sudo manager && \
    echo "manager ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/manager

COPY entrypoint.sh /entrypoint.sh
COPY motd /etc/motd
COPY scripts/ /home/manager/scripts/
RUN chmod +x /entrypoint.sh /home/manager/scripts/*.sh 2>/dev/null; \
    chown -R manager:manager /home/manager
