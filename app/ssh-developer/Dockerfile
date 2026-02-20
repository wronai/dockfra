FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-server git curl jq nano vim tree htop sudo \
    python3 python3-pip python3-venv python3-pytest make ca-certificates && \
    pip3 install --break-system-packages flask pytest requests httpx pyyaml black flake8 && \
    rm -rf /var/lib/apt/lists/*
RUN mkdir -p /run/sshd /shared/tickets /shared/llm && \
    sed -i 's/#Port 22/Port 2222/' /etc/ssh/sshd_config && \
    sed -i 's/#PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config && \
    sed -i 's/#PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config && \
    echo "AllowUsers developer" >> /etc/ssh/sshd_config
RUN useradd -m -s /bin/bash -G sudo developer && \
    echo "developer ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/developer
COPY entrypoint.sh /entrypoint.sh
COPY motd /etc/motd
COPY scripts/ /home/developer/scripts/
RUN chmod +x /entrypoint.sh /home/developer/scripts/*.sh 2>/dev/null; \
    chown -R developer:developer /home/developer
EXPOSE 2222
CMD ["/entrypoint.sh"]
