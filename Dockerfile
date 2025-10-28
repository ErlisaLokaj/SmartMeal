FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install pg_isready (postgres client) so we can wait for the database in the entry command
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy app
COPY . /app

EXPOSE 8000

# Default command — docker-compose will use a small wait loop before starting the app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
