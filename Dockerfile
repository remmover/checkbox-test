FROM python:3.12-slim

WORKDIR /app

# Install system dependencies needed to build some packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

# Upgrade pip and install the Poetry package manager
RUN pip install --upgrade pip && pip install poetry

# Copy dependency management files
COPY pyproject.toml poetry.lock* /app/

# Configure Poetry to install packages globally (without creating a virtual environment)
# and install only the main dependencies (excluding dev dependencies) without installing the root package.
RUN poetry config virtualenvs.create false && \
    poetry install --only main --no-interaction --no-ansi --no-root

# Copy the application code to the container
COPY ./app ./app
# Copy the alembic configuration file into the container
COPY alembic.ini /app/alembic.ini

# Copy the entrypoint.sh script into the container
COPY entrypoint.sh /app/entrypoint.sh
COPY /migrations /app/migrations
# Ensure the entrypoint script is executable
RUN chmod +x /app/entrypoint.sh

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Use the entrypoint.sh script to start the container
CMD ["/app/entrypoint.sh"]
