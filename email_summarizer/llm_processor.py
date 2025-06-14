import json
import os
from typing import Dict, List, Optional
from loguru import logger
import re
import requests
from requests.exceptions import RequestException
from email_summarizer.text_utils import is_bank_transaction, is_positive_transaction
# from models.transaction import FinancialTransaction
# from models.transactionCheck import TransactionCheck
try:
    from .models.transaction import FinancialTransaction
    from .models.transactionCheck import TransactionCheck
    from .database import Transaction, get_session

except ImportError:
    from models.transaction import FinancialTransaction
    from models.transactionCheck import TransactionCheck

class LLMProcessor:
    def __init__(self):
        self.api_base_url = os.getenv('LLM_API_BASE_URL', 'http://localhost:8080/v1')
        self.api_key = os.getenv('LLM_API_KEY')
        self.model = os.getenv('LLM_MODEL', 'gpt-3.5-turbo')
        # if not self.api_key:
        #     raise ValueError("LLM_API_KEY environment variable is required")
        
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # Prompts for transaction detection (is_potential_transaction)
        self.transaction_system_prompt = """Analyse whether the given input indicate a financial transaction 
        relevant to user spending?(e.g., payment, transfer, deposit, withdrawal)?. /no_think"""
        self.detection_prompt_template = """
        Email Subject: {subject}
        Email Sender: {sender}
        {{
            "is_transaction": true/false,
            "confidence": 0.0-1.0,
        }}"""

        self.summarization_system_prompt = """Remove unnecessary text and summarize in less than 100 words. /no_think"""

        # Prompts for extraction
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

    def _call_llm_api(self, messages: list, format: Optional[Dict] = None) -> Dict:
        """Make a call to the LLM API."""

        #logger.info("format: ",format)
        json_data = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.25,
                    "max_tokens": 1024,
                    "top_k":40,
                    "top_p":0.38
        }

        if format:
            json_data["response_format"] = {
                "type":"json_schema",
                "json_schema":{
                    "name":"TransactionCheck",
                    "strict":"true",
                    "schema":format
                }
            }
        
        print(json_data)

        try:
            response = requests.post(
                f"{self.api_base_url}/chat/completions",
                headers=self.headers,
                json=json_data,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            logger.error(f"Error calling LLM API: {str(e)}")
            raise


    def _extract_json_from_response(self, response: Dict, model_class: type) -> Optional[Dict]:
        """Extract and validate JSON from LLM response."""
        try:
            if not response.get('choices'):
                logger.warning("No 'choices' in LLM response.")
                return None
            
            content = response['choices'][0]['message']['content']
            # Remove any <think>...</think> blocks if present
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

            validated_data = model_class.model_validate_json(content)
            return validated_data.model_dump()

        except json.JSONDecodeError:
            logger.error("Failed to parse JSON from LLM response")
            return None
        except Exception as e:
            logger.error(f"Error processing LLM response or validating data: {str(e)}")
            return None

    def summarize_email_content(self, email_body: str) -> str:
        """Summarize email content using LLM. Returns summary text or empty string on failure."""
        try:
            messages = [
                {"role": "system", "content": self.summarization_system_prompt},
                {"role": "user", "content": email_body}
            ]
            
            # Call LLM without specific JSON format for response, expecting text
            response_data = self._call_llm_api(messages) 
            
            if response_data and response_data.get('choices') and \
               len(response_data['choices']) > 0 and \
               response_data['choices'][0].get('message') and \
               response_data['choices'][0]['message'].get('content'):
                
                summary = response_data['choices'][0]['message']['content']
                summary = re.sub(r'<think>.*?</think>', '', summary, flags=re.DOTALL).strip()
                logger.debug(f"Successfully summarized content. Summary length: {len(summary)}")
                return summary
            else:
                logger.warning("LLM response for summarization was empty or malformed.")
                return ""
        except Exception as e:
            logger.error(f"Error during email summarization: {str(e)}")
            return "" # Return empty string on failure

    def process_email(self, subject: str, content: str) -> Dict:
        """Summarize email content, then extract transaction information."""
        default_response = {"amount": 0.0}
        try:
            logger.info("Summarizing email content...")
            summary = self.summarize_email_content(content)
            
            effective_body_content: str
            if summary and summary.strip(): # Check if summary is not None and not just whitespace
                logger.info("Using summarized content for extraction.")
                effective_body_content = summary
            else:
                logger.warning("Summarization failed or returned empty. Using full original content for extraction.")
                effective_body_content = content
            
            if not is_positive_transaction(effective_body_content):
                logger.info("Skipping non positive transaction email.")

            input_for_extraction = self.extraction_input_template.format(
                content=effective_body_content
            )
            messages = [
                {"role": "system", "content": self.extraction_system_prompt},
                {"role": "user", "content": input_for_extraction}
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
            #'RATHER FILTER BANK EMAILS THAN CHECKING SUBJECT'
            logger.info('calling llm bro')
            messages = [
                {"role": "system", "content": self.transaction_system_prompt},
                {"role": "user", "content": self.detection_prompt_template.format(
                    subject=subject,
                    sender=sender
                )}
            ]
            response = self._call_llm_api(messages, TransactionCheck.model_json_schema())
            result = self._extract_json_from_response(response, TransactionCheck)
            
            if result:
                # Assuming TransactionCheck model has 'is_transaction' field
                return result.get('is_transaction', False) 
            return False # Default to False if extraction or validation fails
            
        except Exception as e:
            logger.error(f"Error in transaction detection: {str(e)}")
            # In case of error, be conservative and return True to not miss potential transactions
            return True 
 
    def process_emails(self, emails: List[Dict], status_callback=None) -> List[Dict]:
        """
        Process a list of emails and extract transactions from them.
        
        Args:
            emails (List[Dict]): List of email dictionaries with keys: id, subject, sender, date, body
            status_callback: Optional callback function to update processing status
            
        Returns:
            List[Dict]: List of extracted transactions
        """
        transactions = []
        session = get_session()
        
        if status_callback:
            status_callback(total=len(emails), processed=0, message="Starting email processing")
        
        for i, email in enumerate(emails, 1):
            try:
                # Pre-filter emails using LLM, but don't filter out emails with 'bank' in sender or subject
                # if 'bank' not in email['subject'].lower() and 'bank' not in email['sender'].lower():
                #     # Uncomment this line if we want a LLM to verify using the subject
                #     # if not self.is_potential_transaction(email['subject'], email['sender']):
                #     logger.debug(f"Skipping non-transaction email: {email['subject']}")
                #     continue

                # Hmm.... check if email was already processed
                if session.query(Transaction).filter_by(email_id=email['id']).first():
                    logger.debug(f"Skipping already processed email: {email['subject']}")
                    continue
                
                if not is_bank_transaction(email['body']):
                    logger.info("Skipping non transaction email.", email['sender'])
                    continue
                
                if status_callback:
                    status_callback(
                        processed=i,
                        current=email['subject'],
                        message=f"Processing email {i} of {len(emails)}"
                    )
                
                # Process with LLM
                result = self.process_email(email['subject'], email['body'])
                
                if result['amount'] > 0:
                    # Add email_id to the transaction data
                    result['email_id'] = email['id']
                    transactions.append(result)
                    logger.info(f"Extracted transaction: {result['vendor']} - {result['amount']} {result['type']}")
                
            except Exception as e:
                logger.error(f"Error processing email {email['id']}: {str(e)}")
                continue
        
        if status_callback:
            status_callback(message="Email processing complete")
        
        return transactions 