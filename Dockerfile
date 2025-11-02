FROM python:3.11-slim

WORKDIR /app

# Environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies
# - postgresql-client: for pg_isready health checks
# - curl: for application health checks
# - dos2unix: for converting Windows line endings to Unix (or use sed)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# Copy requirements first for better Docker layer caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

# Copy application code
# The new architecture follows this structure:
# - adapters/: External service connections (Neo4j, MongoDB, SQL)
# - api/: REST API routes and middleware
# - core/: Configuration and exceptions
# - domain/: Domain models, schemas, and mappers
# - repositories/: Data access layer
# - services/: Business logic layer
# - scripts/: Utility scripts
# - data/: Data files for seeding
COPY . /app

# Convert line endings and make entrypoint executable
# This fixes the "no such file or directory" error on Windows
RUN sed -i 's/\r$//' /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh

EXPOSE 8000

# Entrypoint handles service health checks and database initialization
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command starts the FastAPI application with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

