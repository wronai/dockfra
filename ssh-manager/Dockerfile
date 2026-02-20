FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-server openssh-client git curl jq nano vim tree sudo \
    python3 python3-pip ca-certificates && \
    pip3 install --break-system-packages requests pyyaml && \
    rm -rf /var/lib/apt/lists/*
RUN mkdir -p /run/sshd /shared/tickets /shared/llm && \
    sed -i 's/#Port 22/Port 2222/' /etc/ssh/sshd_config && \
    sed -i 's/#PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config && \
    sed -i 's/#PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config && \
    echo "AllowUsers manager" >> /etc/ssh/sshd_config
RUN useradd -m -s /bin/bash -G sudo manager && \
    echo "manager ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/manager
COPY entrypoint.sh /entrypoint.sh
COPY motd /etc/motd
COPY manager-scripts/ /home/manager/scripts/
RUN chmod +x /entrypoint.sh /home/manager/scripts/*.sh 2>/dev/null; \
    chown -R manager:manager /home/manager
EXPOSE 2222
CMD ["/entrypoint.sh"]
