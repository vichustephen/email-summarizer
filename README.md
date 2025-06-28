# Transaction Email Summarizer

**Minimal design (Tested on  Raspberry Pi 4 2GB with Qwen3 0.6b using llama cpp) automated extraction & summarisation of transaction e-mails powered by a local LLM and a modern browser dashboard.**

TESTED ON HDFC/INDUSIND BANK EMAILS WILL UPDATE SOON ON OTHER BANK EMAILS

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg) ![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-teal.svg) ![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-purple.svg) ![Docker](https://img.shields.io/badge/Docker-ready-blue.svg)

---
## Prerequisites

- Raspberry Pi (4 or newer recommended) Or you can use docker on any system
- Python 3.8 or newer
- Gmail account with APP password or OAuth 2.0 credentials
- llama cpp build or any local llm

## 1. Quick-start

Please Setup and install llamacpp or ollama or any other local LLM and **Important properly update the ENV**

### 1.1 Run with Docker Compose

```bash

# Copy & edit configuration
$ cp .env.example .env         # edit with your secrets & paths

# Run container – maps ports & mounts your local model
$ docker-compose up
```

### 1.2 Run with Docker

```bash
# Build image (one-off)
$ docker build -t email-summarizer .

# Copy & edit configuration
$ cp .env.example .env         # edit with your secrets & paths

# Run container – maps ports & mounts your local model
$ docker run -it --rm \
    -p 8000:8000 -p 3000:3000 \
    --env-file .env \
    -v $PWD/data:/app/data \
    -v $PWD/models:/app/models \
    email-summarizer

# Windows
$ docker run -it --rm ^
    -p 8000:8000 -p 3000:3000 ^
    --env-file .env ^
    -v "%cd%\data:/app/data" ^
    -v "%cd%\models:/app/models" ^
    email-summarizer
```


Open your browser at **http://localhost:3000** (frontend)

### 1.3 Local development (no Docker)

```bash

python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn email_summarizer.api:app --reload

python run.py
```

---

## 2. LLM Setup
This project relies on a **local Large Language Model** to parse natural-language e-mails and extract the monetary transactions inside them.  
We recommend [**llama.cpp**](https://github.com/ggerganov/llama.cpp) because it is lightweight, open-source and runs fully offline.

1. Install llama.cpp using the instructions provided [here](https://github.com/ggerganov/llama.cpp#installation). (Best for Raspberry Pi)

## 2.1 LLM Configuration

The summariser **will not start** unless it can load the model.

### 2.1.1 LLM Provider

Set the ENV `LLM_PROVIDER` to one of the following:

- `llama` to use `LlamaCppProcessor` with a local LLM model.
- `openai` to use `LLMProcessor` which can connect to any OpenAI-based LLM e.g OLLAMA, llama.cpp server

*IMPORTANT* If using  `llama` as LLM model, download your preferred gguf from hugging face and put it in the models directory

If using an `openai` LLM model, set the ENV `LLM_API_BASE_URL` to the base URL of the LLM API. E.g Ollama or Lm studio or llama.cpp server. AND set the ENV `LLM_MODEL` to the model name you want to use.
*Cloud LLMS are not recommended* as email processing contains sensitive information. 
Example:
LLM_API_BASE_URL=http://localhost:11434/v1
LLM_MODEL=qwen3:0.6b

## 3. Architecture

```
┌──────────────┐      WebSocket / REST      ┌────────────────┐
│  Front-end   │  <---------►                │ FastAPI back-end│
│ Bootstrap 5  │                            │  Summariser     │
└──────────────┘                            └────────────────┘
       ▲                                             │
       │                                             ▼
   HTTP 3000                                 llama.cpp (local)
```

* **Frontend** – Static HTML/JS served via a lightweight Python HTTP server (or any CDN).  Provides a dashboard for scheduling, manual date-range processing, live progress bar, and history browsing.
* **Backend** – FastAPI application (`email_summarizer.api`) exposing REST & WebSocket endpoints.
* **Scheduler** – Background thread processes the inbox periodically or on demand.
* **Local LLM** – llama.cpp or ollama or LMstudio

---

## 4. Key Features

* 📅 Automatic & manual date-range processing
* 💾 Flexible database storage (SQLite, PostgreSQL, etc.)
* 📨 Optional e-mail notifications
* 🐳 Docker-first deployment

---

## 5. Configuration (.env)

To configure the application, copy the `.env.example` file to `.env` and set the appropriate environment variables. Ensure you replace placeholder values with your actual credentials and settings.

```
# General
LOG_LEVEL=INFO
LOG_FILE=/app/logs/email_summarizer.log

# Database
DATABASE_URL=sqlite:////app/data/transactions.db # Use an appropriate connection string for your database, e.g., postgresql+psycopg://user:password@host:port/dbname

# E-mail
IMAP_SERVER=imap.gmail.com
IMAP_PORT=993
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_USERNAME=your_email@gmail.com

#SET TO FALSE TO DISABLE OAUTH AND USE APP PASSWORD
OAUTH_ENABLED=False

#FOR OAUTH
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

#FOR APP PASSWORD
EMAIL_PASSWORD=your_app_password

# Frontend
FRONTEND_PORT=3000
```
> Environment names match the keys consumed in `email_summarizer.main` and `email_summarizer.api`.

---

## Gmail Connection Methods

You can connect to your Gmail account using either OAuth 2.0 or a Google App Password. Choose the method that best suits your needs.

### Option 1: OAuth 2.0 Setup for Gmail (Not tested yet)

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Gmail API
4. Create OAuth 2.0 credentials:
   - Create OAuth client ID
   - Select Desktop application
   - Download the client configuration file (usually `credentials.json`)
5. Update the `.env` file with your client ID and secret, or ensure `credentials.json` is accessible to the application.

### Option 2: Google App Password Setup for Gmail

If you have 2-Step Verification enabled on your Google Account, you can use an App Password to allow the application to access your Gmail. This is often simpler for automated systems.

1. Go to your [Google Account Security page](https://myaccount.google.com/apppasswords?continue=https%3A%2F%2Fmyaccount.google.com%2Fsecurity).
2. * If you don't see "App passwords," it might be because:
     * 2-Step Verification is not set up for your account.
     * 2-Step Verification is only set up for security keys.
     * Your account is through work, school, or other organization.
     * You've turned on Advanced Protection.
4. Enter a name like "Email Summarizer" and click **GENERATE**.
5. A 16-character code in a yellow bar will appear. This is your App Password. Copy this password.
6. In your `.env` file, set `EMAIL_ADDRESS` to your Gmail address and `EMAIL_PASSWORD` to this generated App Password.

---

## 6. Useful commands

* **Build & run Docker** – see *Quick-start* above.
* **Database** (inside container):
  ```bash
  sqlite3 /app/data/transactions.db
  ```
* **Logs**: `tail -f logs/email_summarizer.log`

---

## OAuth 2.0 Setup for Gmail

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Gmail API
4. Create OAuth 2.0 credentials:
   - Create OAuth client ID
   - Select Desktop application
   - Download the client configuration file
5. Update the .env file with your client ID and secret


## Troubleshooting

1. LLM Issues:
   - Ensure your model file is compatible with llama.cpp
   - Check RAM usage and adjust MODEL_N_CTX if needed
   - Verify model file permissions

2. Email Connection Issues:
   - Verify OAuth 2.0 credentials
   - Check network connectivity
   - Ensure IMAP is enabled in Gmail settings

3. Database Issues:
   - Check write permissions for SQLite database
   - Verify database path in configuration
   - Monitor disk space

<!-- Windowns llama.cpp setup
set CMAKE_GENERATOR=MinGW Makefiles
set CMAKE_ARGS=-DGGML_OPENBLAS=on -DCMAKE_C_COMPILER=D:/ProgramFiles/w64devkit/bin/gcc.exe -DCMAKE_CXX_COMPILER=D:/ProgramFiles/w64devkit/bin/g++.exe -DCMAKE_MAKE_PROGRAM=D:/ProgramFiles/w64devkit/bin/make.exe -->

## License

This project is licensed under the MIT License - see the LICENSE file for details. 
