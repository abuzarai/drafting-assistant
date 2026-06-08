FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies first for better build cache reuse
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

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

EXPOSE 8080
CMD ["sh", "-c", "python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
