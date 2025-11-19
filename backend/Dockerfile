# syntax=docker/dockerfile:1

FROM python:3.13-slim AS base
WORKDIR /app

# Builder stage: install dependencies in a venv
FROM base AS builder
WORKDIR /app

# Copy only requirements.txt first for better caching
COPY --link requirements.txt ./

# Create virtual environment and install dependencies
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m venv .venv && \
    .venv/bin/pip install --upgrade pip && \
    .venv/bin/pip install -r requirements.txt

# Copy the rest of the application code
COPY --link . .

# Final stage: minimal image with non-root user
FROM base AS final
WORKDIR /app

# Create non-root user
RUN addgroup --system appgroup && adduser --system --group appuser
USER appuser

# Copy app code and venv from builder
COPY --from=builder /app /app
COPY --from=builder /app/.venv /app/.venv

# Activate venv
ENV PATH="/app/.venv/bin:$PATH"

# Entrypoint (adjust if main.py is not the entrypoint)
CMD ["python", "main.py"]
