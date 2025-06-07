#!/bin/bash

# Start the Python HTTP server for frontend in the background
cd /app/frontend && python -m http.server ${FRONTEND_PORT:-3000} &

# Start the FastAPI backend
cd /app && uvicorn email_summarizer.api:app --host 0.0.0.0 --port 8000 