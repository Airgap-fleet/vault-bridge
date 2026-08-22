# AFaaS Vault Bridge — Dockerfile

FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install package
COPY dist/vault_bridge-1.0.0-py3-none-any.whl .
RUN pip install --no-cache-dir vault_bridge-1.0.0-py3-none-any.whl

# Runtime stage
FROM python:3.11-slim-bookworm

WORKDIR /app

# Create non-root user
RUN groupadd -r mcp && useradd -r -g mcp -u 10001 -s /sbin/nologin mcp

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy installed package from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/vault-bridge /usr/local/bin/vault-bridge

# Create vault directory with correct permissions
RUN mkdir -p /vault && chown mcp:mcp /vault

# Switch to non-root user
USER mcp

# Environment defaults
ENV VAULT_BRIDGE_VAULT_PATH=/vault
ENV VAULT_BRIDGE_TRANSPORT=stdio
ENV VAULT_BRIDGE_LOG_LEVEL=INFO
ENV VAULT_BRIDGE_MAX_FILE_SIZE=10485760
ENV VAULT_BRIDGE_FOLLOW_SYMLINKS=false

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import obsidian_mcp; print('OK')" || exit 1

# Expose ports for SSE/HTTP transports
EXPOSE 8000

# Volume for vault
VOLUME ["/vault"]

# Entry point
ENTRYPOINT ["vault-bridge"]