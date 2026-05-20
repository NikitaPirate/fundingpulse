# ── base ──────────────────────────────────────────────────────────────────────
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md alembic.ini ./
COPY fundingpulse/ ./fundingpulse/

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# ── tracker ───────────────────────────────────────────────────────────────────
FROM base AS tracker

RUN apt-get update && apt-get install -y supervisor && rm -rf /var/lib/apt/lists/*

COPY deploy/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]

# ── api ───────────────────────────────────────────────────────────────────────
FROM base AS api

EXPOSE 8000

CMD ["uvicorn", "fundingpulse.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ── migrate ───────────────────────────────────────────────────────────────────
FROM base AS migrate

CMD ["alembic", "upgrade", "head"]
