# syntax=docker/dockerfile:1.7
FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.title="Maine Family Law LLM" \
      org.opencontainers.image.description="Standalone Maine family-law legal AI API container; external legal data is mounted at /data." \
      org.opencontainers.image.source="https://example.invalid/maine-family-law-llm" \
      org.opencontainers.image.licenses="see LICENSE.md"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    MAINE_FAMILY_LAW_DATA_ROOT=/data \
    UVICORN_HOST=0.0.0.0 \
    UVICORN_PORT=8000

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /home/app --create-home app \
    && mkdir -p /app /data /tmp/mfll \
    && chown -R app:app /app /data /tmp/mfll

WORKDIR /app

COPY --chown=app:app pyproject.toml README.md LICENSE.md ./
COPY --chown=app:app app ./app
COPY --chown=app:app legal ./legal
COPY --chown=app:app configs ./configs
COPY --chown=app:app scripts ./scripts

RUN python -m pip install --upgrade pip \
    && python -m pip install '.[api]'

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python /app/scripts/container-healthcheck.py --url "http://127.0.0.1:${UVICORN_PORT}/api/health"

CMD ["sh", "-c", "uvicorn app.api.main:app --host ${UVICORN_HOST} --port ${UVICORN_PORT}"]
