import json
import os
from typing import Dict, Optional, Union
from loguru import logger
from datetime import datetime
import re
import requests
from requests.exceptions import RequestException

class LLMProcessor:
    def __init__(self):
        self.api_base_url = os.getenv('LLM_API_BASE_URL', 'http://localhost:8080/v1')
        self.api_key = os.getenv('LLM_API_KEY')
        self.model = os.getenv('LLM_MODEL', 'gpt-3.5-turbo')
        
        if not self.api_key:
            raise ValueError("LLM_API_KEY environment variable is required")
        
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        self.transaction_system_prompt = """You are a transaction detection and analysis system. 
        Your task is to analyze email content and extract transaction information accurately.
        You should respond in JSON format only."""
        
        self.transaction_prompt_template = """Analyze the following email content and determine if it contains transaction information.
        If it does, extract the relevant details in JSON format. If not, return {"is_transaction": false}.

        Email Subject: {subject}
        Email Content: {content}

        Required JSON format for transactions:
        {
            "is_transaction": true,
            "vendor": "string",
            "amount": float,
            "currency": "string",
            "description": "string",
            "category": "string",
            "transaction_date": "YYYY-MM-DD"
        }

        Categories should be one of: Food & Drink, Shopping, Bills, Travel, Entertainment, Other

        Respond with valid JSON only."""

        self.detection_prompt_template = """Analyze this email and determine if it's likely to contain transaction information.
        Consider the context, language, and typical patterns of transaction emails.
        
        Email Subject: {subject}
        Email Sender: {sender}
        
        Respond with valid JSON only in this format:
        {
            "is_potential_transaction": boolean,
            "confidence": float,  # between 0 and 1
            "reasoning": "string"
        }"""

    def _call_llm_api(self, messages: list) -> Dict:
        """Make a call to the LLM API."""
        try:
            response = requests.post(
                f"{self.api_base_url}/chat/completions",
                headers=self.headers,
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.1,
                    "max_tokens": 512
                },
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            logger.error(f"Error calling LLM API: {str(e)}")
            raise

    def _clean_text(self, text: str) -> str:
        """Clean and prepare text for LLM processing."""
        # Remove multiple whitespaces and newlines
        text = re.sub(r'\s+', ' ', text)
        # Remove email signatures and footers (common patterns)
        text = re.sub(r'Best regards,.*$', '', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'Sent from.*$', '', text, flags=re.IGNORECASE | re.DOTALL)
        return text.strip()

    def _extract_json_from_response(self, response: Dict) -> Dict:
        """Extract and validate JSON from LLM response."""
        try:
            if not response.get('choices'):
                return {"is_transaction": False}
            
            content = response['choices'][0]['message']['content']
            data = json.loads(content)
            
            # Validate required fields for transactions
            if data.get("is_transaction"):
                required_fields = [
                    "vendor", "amount", "currency", "description",
                    "category", "transaction_date"
                ]
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
            cleaned_content = self._clean_text(content)
            cleaned_subject = self._clean_text(subject)
            
            messages = [
                {"role": "system", "content": self.transaction_system_prompt},
                {"role": "user", "content": self.transaction_prompt_template.format(
                    subject=cleaned_subject,
                    content=cleaned_content
                )}
            ]
            
            response = self._call_llm_api(messages)
            return self._extract_json_from_response(response)
            
        except Exception as e:
            logger.error(f"Error processing email with LLM: {str(e)}")
            return {"is_transaction": False}

    def is_potential_transaction(self, subject: str, sender: str) -> bool:
        """Use LLM to determine if an email is potentially a transaction."""
        try:
            messages = [
                {"role": "system", "content": self.transaction_system_prompt},
                {"role": "user", "content": self.detection_prompt_template.format(
                    subject=subject,
                    sender=sender
                )}
            ]
            
            response = self._call_llm_api(messages)
            result = self._extract_json_from_response(response)
            
            # Consider it a potential transaction if confidence is > 0.6
            return result.get('is_potential_transaction', False) and result.get('confidence', 0) > 0.6
            
        except Exception as e:
            logger.error(f"Error in transaction detection: {str(e)}")
            # In case of error, be conservative and return True to not miss potential transactions
            return True 