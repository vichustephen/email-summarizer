import json
import os
from typing import Dict, List, Optional
from loguru import logger
from datetime import datetime
import re
import requests
from requests.exceptions import RequestException
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
        
        self.transaction_system_prompt = """Analyse whether the given input indicate a financial transaction 
        relevant to user spending?(e.g., payment, transfer, deposit, withdrawal)? (Yes/No). /no_think"""

        self.extraction_system_prompt = """You are a helpful assistant that extracts transaction information from bank emails.
Given an email, extract the following in JSON format:
  {
    "amount": (float),
    "type": "(credit or debit)",
    "vendor": " (merchant or where amount is spent)",
    "date": "2024-08-15",
    "ref": "(transaction id or ref number)",
    "category": "Categories should be one of: Food & Drink, Shopping, Bills, Travel, Entertainment, Other"
  } /no_think"""
        
        self.transaction_prompt_template = """Content: {content}"""

        self.detection_prompt_template = """
        Email Subject: {subject}
        Email Sender: {sender}
        {{
            "is_transaction": true/false,
            "confidence": 0.0-1.0,
        }}"""

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


    def _extract_json_from_response(self, response: Dict, required_fields:List[str]) -> Dict:
        """Extract and validate JSON from LLM response."""
        try:
            if not response.get('choices'):
                return {"is_transaction": False}
            
            content = response['choices'][0]['message']['content']
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            data = json.loads(content)
            
            # Validate required fields for transactions
            if data.get("is_transaction"):
                if not all(field in data for field in required_fields):
                    logger.warning("Missing required fields in transaction data")
                    return {"is_transaction": False}
                
                # Validate date format
                try:
                    datetime.strptime(data["transaction_date"], "%Y-%m-%d")
                except ValueError:
                    logger.warning("Invalid date format in transaction data")
                    return {"is_transaction": False}
            
            return data
        except json.JSONDecodeError:
            logger.error("Failed to parse JSON from LLM response")
            return {"is_transaction": False}
        except Exception as e:
            logger.error(f"Error processing LLM response: {str(e)}")
            return {"is_transaction": False}

    def process_email(self, subject: str, content: str) -> Dict:
        """Process email content and extract transaction information."""
        try:
            # Clean the input text
            #cleaned_content = self._clean_text(content)
            #cleaned_subject = self._clean_text(subject)
            
            messages = [
                {"role": "system", "content": self.extraction_system_prompt},
                {"role": "user", "content": self.transaction_prompt_template.format(
                    subject=subject,
                    content=content
                )}
            ]
            
            response = self._call_llm_api(messages, FinancialTransaction.model_json_schema())
            return self._extract_json_from_response(response,[
                    "vendor", "amount", "type", "ref",
                    "category", "date" 
                ])
            
        except Exception as e:
            logger.error(f"Error processing email with LLM: {str(e)}")
            return {"is_transaction": False}

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
            result = self._extract_json_from_response(response,['is_transaction','confidence'])
            
            return result.get('is_potential_transaction', False)
            
        except Exception as e:
            logger.error(f"Error in transaction detection: {str(e)}")
            # In case of error, be conservative and return True to not miss potential transactions
            return True 