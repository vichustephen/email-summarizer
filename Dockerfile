# Use Python 3.11 slim image for a smaller footprint
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY email_summarizer/ email_summarizer/
COPY frontend/ frontend/
COPY run.py .

# Create necessary directories and set permissions
RUN mkdir -p /app/data /app/logs \
    && touch /app/data/transactions.db \
    && chmod -R 755 /app/data /app/logs

# Create a non-root user
RUN useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

# Set default environment variables
ENV DATABASE_URL=sqlite:////app/data/transactions.db \
    LOG_FILE=/app/logs/email_summarizer.log \
    LOG_LEVEL=INFO \
    IMAP_SERVER=imap.gmail.com \
    IMAP_PORT=993 \
    SMTP_SERVER=smtp.gmail.com \
    SMTP_PORT=587 \
    BATCH_SIZE=20 \
    PROCESSING_INTERVAL_HOURS=4 \
    SUMMARY_TIME=23:00 \
    FRONTEND_PORT=3000

# Expose both backend and frontend ports
EXPOSE 8000 3000

# Copy the startup script
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Use the startup script as entrypoint
ENTRYPOINT ["/app/start.sh"] 