FROM node:22-slim

RUN apt-get update && apt-get install -y python3 python3-pip curl && \
    rm -rf /var/lib/apt/lists/*

# Install OpenClaw
RUN curl -fsSL https://openclaw.ai/install.sh | bash || true

WORKDIR /app

# Copy workspace
COPY openclaw-workspace/ /app/openclaw-workspace/
COPY scripts/ /app/scripts/
COPY config.json /app/config.json

RUN chmod +x /app/scripts/*.py /app/scripts/*.sh 2>/dev/null || true

EXPOSE 18789

WORKDIR /app/openclaw-workspace
ENTRYPOINT ["openclaw", "start"]
