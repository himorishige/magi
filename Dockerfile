FROM node:22-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Python venv + dependencies
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir requests

# Install OpenClaw via npm (more reliable in Docker than curl installer)
RUN npm install -g openclaw@latest && \
    pnpm approve-builds -g 2>/dev/null || true

WORKDIR /app

# Copy workspace and scripts
COPY openclaw-workspace/ ./openclaw-workspace/
COPY scripts/ ./scripts/
COPY config.json ./config.json
COPY data/ ./data/

RUN chmod +x scripts/*.py scripts/*.sh 2>/dev/null || true

EXPOSE 18789

WORKDIR /app/openclaw-workspace
ENV OPENCLAW_CONFIG_PATH=/app/openclaw-workspace/openclaw.json

CMD ["openclaw", "gateway", "--allow-unconfigured"]
