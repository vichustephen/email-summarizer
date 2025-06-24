"""Defines the base class for LLM processors to share common logic.

This abstract base class provides the core structure and duplicated code
for processing emails, extracting transactions, and summarizing content.

Concrete implementations must provide their own `_call_llm_api` method,
as the mechanism for communicating with the LLM is the key difference
between them (e.g., a local `llama.cpp` instance vs. a remote HTTP API).
"""
from __future__ import annotations

import abc
from typing import Dict, List, Optional

from loguru import logger

from email_summarizer.llm_utils import extract_json_from_response
from email_summarizer.text_utils import is_bank_transaction, is_positive_transaction

try:
    from .database import Transaction, get_session
    from .models.transaction import FinancialTransaction
    from .models.transactionCheck import TransactionCheck
except ImportError:
    # Fallback for when running outside a package context
    from database import Transaction, get_session  # type: ignore
    from models.transaction import FinancialTransaction  # type: ignore
    from models.transactionCheck import TransactionCheck  # type: ignore


class BaseProcessor(abc.ABC):
    """Abstract base class for LLM processors."""

    def __init__(self):
        """Initialize the processor and set up the shared prompts."""
        self.transaction_system_prompt = (
            "Analyse whether the given input indicate a financial transaction "
            "relevant to user spending?(e.g., payment, transfer, deposit, withdrawal)?. /no_think"
        )
        self.detection_prompt_template = """
        Email Subject: {subject}
        Email Sender: {sender}
        {{
            "is_transaction": true/false,
            "confidence": 0.0-1.0,
        }}"""

        self.summarization_system_prompt = (
            "Remove unnecessary text and summarize in less than 100 words.Do no miss any transaction details. /no_think"
        )

        self.extraction_system_prompt = """You are a helpful assistant that extracts transaction information from bank emails.
Given an email, extract the following:
        {
            "amount": (float),
            "type": "(credit or debit)",
            "vendor": " (merchant or where amount is spent)",
            "date": "2024-08-15",
            "ref": "(transaction id or ref number)",
            "category": "Categories should be one of: Food & Drink, Shopping, Bills, Travel, Entertainment, Other"
        } If not found or failed or unsuccessful set amount to 0 /no_think"""
        self.extraction_input_template = """Content: {content}"""

    @abc.abstractmethod
    def _call_llm_api(self, messages: list, format: Optional[Dict] = None) -> Dict:
        """Abstract method to make a call to the underlying LLM API.

        Subclasses must implement this method to handle the specifics of their
        LLM communication (e.g., local binding vs. remote HTTP API).
        """
        raise NotImplementedError

    def _extract_json_from_response(self, response: Dict, model_class: type) -> Optional[Dict]:
        """Delegate to shared utility function to avoid code duplication."""
        return extract_json_from_response(response, model_class)

    def summarize_email_content(self, email_body: str) -> str:
        """Summarize email content using LLM. Returns summary text or empty string on failure."""
        try:
            messages = [
                {"role": "system", "content": self.summarization_system_prompt},
                {"role": "user", "content": email_body},
            ]

            response_data = self._call_llm_api(messages)

            if not (response_data and response_data.get("choices")):
                return ""

            choice = response_data["choices"][0]
            summary = ""
            if isinstance(choice, dict):
                # Handles OpenAI format: `choices[0]['message']['content']`
                if message := choice.get("message", {}):
                    if isinstance(message, dict):
                        summary = message.get("content", "")
                # Handles llama.cpp format: `choices[0]['text']`
                if not summary:
                    summary = choice.get("text", "")

            return summary.strip()

        except Exception as e:
            logger.error(f"Error summarizing email content: {str(e)}")
            return ""

    def process_email(self, subject: str, content: str) -> Dict:
        """Summarize email content, then extract transaction information."""
        default_response = {"amount": 0.0}
        try:
            logger.info("Summarizing email content...")
            summary = self.summarize_email_content(content)

            effective_body_content = summary if summary and summary.strip() else content
            if summary and summary.strip():
                logger.info("Using summarized content for extraction.")
            else:
                logger.warning("Summarization failed. Using full content for extraction.")

            if not is_positive_transaction(effective_body_content):
                logger.info("Skipping non-positive transaction email.")

            input_for_extraction = self.extraction_input_template.format(content=effective_body_content)
            messages = [
                {"role": "system", "content": self.extraction_system_prompt},
                {"role": "user", "content": input_for_extraction},
            ]

            response = self._call_llm_api(messages, FinancialTransaction.model_json_schema())
            extracted_data = self._extract_json_from_response(response, FinancialTransaction)

            return extracted_data if extracted_data else default_response

        except Exception as e:
            logger.error(f"Error processing email with LLM: {str(e)}")
            return default_response

    def is_potential_transaction(self, subject: str, sender: str) -> bool:
        """Use LLM to determine if an email is potentially a transaction."""
        try:
            logger.info("Checking if email is a potential transaction...")
            messages = [
                {"role": "system", "content": self.transaction_system_prompt},
                {
                    "role": "user",
                    "content": self.detection_prompt_template.format(subject=subject, sender=sender),
                },
            ]
            response = self._call_llm_api(messages, TransactionCheck.model_json_schema())
            result = self._extract_json_from_response(response, TransactionCheck)

            if result:
                return result.get("is_transaction", False)
            return False

        except Exception as e:
            logger.error(f"Error in transaction detection: {str(e)}")
            # Be conservative and return True to not miss potential transactions
            return True

    def process_emails(self, emails: List[Dict], status_callback=None) -> List[Dict]:
        """Process a list of emails and extract transactions from them."""
        transactions = []
        session = get_session()

        if status_callback:
            status_callback(total=len(emails), processed=0, message="Starting email processing")

        for i, email in enumerate(emails, 1):
            try:
                if session.query(Transaction).filter_by(email_id=email["id"]).first():
                    logger.debug(f"Skipping already processed email: {email['subject']}")
                    continue

                if not is_bank_transaction(email["body"]):
                    logger.info(f"Skipping non-transaction email from {email['sender']}.")
                    continue

                if status_callback:
                    status_callback(
                        processed=i,
                        current=email["subject"],
                        message=f"Processing email {i} of {len(emails)}",
                    )

                result = self.process_email(email["subject"], email["body"])

                if result.get("amount", 0) > 0:
                    result["email_id"] = email["id"]
                    transactions.append(result)
                    logger.info(f"Extracted transaction: {result.get('vendor')} - {result.get('amount')} {result.get('type')}")

            except Exception as e:
                logger.error(f"Error processing email {email['id']}: {str(e)}")
                continue

        if status_callback:
            status_callback(message="Email processing complete")

        return transactions
