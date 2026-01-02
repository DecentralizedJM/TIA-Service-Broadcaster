FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy source code
COPY src/ src/

# Create data directory for SQLite
RUN mkdir -p /app/data

ENV DATABASE_PATH=/app/data/subscribers.db

# Expose port
EXPOSE 8000

# Run the server
CMD ["python", "-m", "signal_bot.run"]
