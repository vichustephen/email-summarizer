FROM python:3.11-slim

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system and build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    libpq-dev \
    curl \
    build-essential \
    cmake \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# you can change the spacy pipepine here
RUN python -m spacy download en_core_web_sm 

# Remove build dependencies to reduce image size
RUN apt-get purge -y --auto-remove build-essential cmake && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY email_summarizer/ email_summarizer/
COPY frontend/ frontend/
COPY run.py .

# Create necessary directories and set permissions
RUN mkdir -p /app/data /app/logs /app/models \
    && touch /app/data/transactions.db \
    && chmod -R 755 /app/data /app/logs /app/models

# Create a non-root user
# RUN useradd -m -u 1000 appuser \
#     && chown -R appuser:appuser /app
# USER appuser

# Set default environment variables
ENV DATABASE_URL=sqlite:////app/data/transactions.db \
    LOG_FILE=/app/logs/email_summarizer.log \
    LOG_LEVEL=INFO \
    IMAP_SERVER=imap.gmail.com \
    IMAP_PORT=993 \
    SMTP_SERVER=smtp.gmail.com \
    SMTP_PORT=587 \
    FRONTEND_PORT=3000 \
    LLAMA_MODEL_PATH=/app/models/Qwen_Qwen3-0.6B-Q4_K_S.gguf

# 8000 is backend 3000 frontend ports
EXPOSE 8000 3000

COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

ENTRYPOINT ["/app/start.sh"] 