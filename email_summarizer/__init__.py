"""
Email Transaction Summarizer Agent
--------------------------------

A Python-based email summarizer agent that automatically processes emails,
extracts transaction information using a local LLM, and sends daily summaries.
"""

__version__ = '0.1.0'
__author__ = 'Vishnu Kumar'
__license__ = 'MIT'

from . import database
from . import main
from . import notifier
from . import llm_processor
from . import email_client

from .main import (
    configure_schedule,
    get_last_run_time,
    get_next_run_time,
    process_date_range,
    start_summarizer,
    stop_summarizer,
    is_running,
    get_processing_status
)

from .database import (
    get_session,
    get_daily_summaries,
    get_transactions_by_date_range
) 