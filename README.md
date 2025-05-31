# Email Transaction Summarizer Agent

A Python-based email summarizer agent designed for Raspberry Pi that automatically processes emails, extracts transaction information using a local LLM, and sends daily summaries.

## Features

- Email Processing:
  - IMAP connection with OAuth 2.0 authentication
  - Automatic email fetching and processing
  - Smart pre-filtering of transaction-related emails
  
- LLM Integration:
  - Local LLM processing using llama.cpp
  - Efficient transaction information extraction
  - Support for various LLM models (Phi-3 Mini, Llama 3 8B, etc.)
  
- Transaction Management:
  - SQLite database for transaction storage
  - Automatic categorization of transactions
  - Duplicate detection using email IDs
  
- Daily Summaries:
  - Automated daily transaction summaries
  - Category-wise spending breakdown
  - Multi-currency support
  - Beautiful HTML email reports

## Prerequisites

- Raspberry Pi (4 or newer recommended)
- Python 3.8 or newer
- A compatible GGUF model file (e.g., Phi-3 Mini or Llama 3 8B)
- Gmail account with OAuth 2.0 credentials
- Sufficient storage space for the LLM model

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd email-summarizer
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   ```
   Edit the `.env` file with your configuration:
   - Email credentials
   - OAuth 2.0 settings
   - LLM model path and settings
   - Processing intervals
   - Notification settings

5. Download a GGUF model:
   - Visit [HuggingFace](https://huggingface.co/) to download a compatible GGUF model
   - Place the model file in your desired location
   - Update the MODEL_PATH in your .env file

## OAuth 2.0 Setup for Gmail

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Gmail API
4. Create OAuth 2.0 credentials:
   - Create OAuth client ID
   - Select Desktop application
   - Download the client configuration file
5. Update the .env file with your client ID and secret

## Usage

1. Start the agent:
   ```bash
   python -m email_summarizer.main
   ```

2. The agent will:
   - Process emails every 4 hours (configurable)
   - Send daily summaries at 23:00 (configurable)
   - Log activities to email_summarizer.log

3. Monitor the logs:
   ```bash
   tail -f email_summarizer.log
   ```

## Setting up as a Service

1. Create a systemd service file:
   ```bash
   sudo nano /etc/systemd/system/email-summarizer.service
   ```

2. Add the following content:
   ```ini
   [Unit]
   Description=Email Transaction Summarizer Agent
   After=network.target

   [Service]
   Type=simple
   User=pi
   WorkingDirectory=/path/to/email-summarizer
   Environment=PATH=/path/to/email-summarizer/venv/bin
   ExecStart=/path/to/email-summarizer/venv/bin/python -m email_summarizer.main
   Restart=always
   RestartSec=300

   [Install]
   WantedBy=multi-user.target
   ```

3. Enable and start the service:
   ```bash
   sudo systemctl enable email-summarizer
   sudo systemctl start email-summarizer
   ```

## Configuration Options

### Email Processing
- `BATCH_SIZE`: Number of emails to process in each batch
- `PROCESSING_INTERVAL_HOURS`: Hours between email processing runs

### LLM Settings
- `MODEL_PATH`: Path to your GGUF model file
- `MODEL_N_CTX`: Context window size
- `MODEL_N_THREADS`: Number of threads for LLM processing

### Notification Settings
- `SUMMARY_TIME`: Time for daily summary (24-hour format)
- `SMTP_SERVER`: SMTP server for sending notifications
- `SMTP_PORT`: SMTP port number

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

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 