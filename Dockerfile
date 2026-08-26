FROM python:3.11-slim

# Install uv (standalone binary; pin for reproducibility)
COPY --from=ghcr.io/astral-sh/uv:0.5.14 /uv /uvx /bin/

WORKDIR /app

# Install dependencies first for better build cache reuse
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy only API/runtime code needed in production image
COPY main.py config.py ./
COPY db ./db
COPY models ./models
COPY prompts ./prompts
COPY routes ./routes
COPY services ./services

# Run as non-root
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Prefer the project venv (uv sync created .venv)
ENV PATH="/app/.venv/bin:${PATH}"

EXPOSE 8080
CMD ["sh", "-c", "python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]