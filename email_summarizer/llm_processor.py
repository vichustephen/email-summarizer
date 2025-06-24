import os
from typing import Dict, Optional

import requests
from loguru import logger
from requests.exceptions import RequestException

from email_summarizer.base_processor import BaseProcessor


class LLMProcessor(BaseProcessor):
    """Processor that uses a remote, OpenAI-compatible API."""

    def __init__(self):
        """Initialize the LLMProcessor."""
        super().__init__()
        self.api_base_url = os.getenv("LLM_API_BASE_URL", "http://localhost:8080/v1")
        self.api_key = os.getenv("LLM_API_KEY")
        self.model = os.getenv("LLM_MODEL", "gpt-3.5-turbo")

        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _call_llm_api(self, messages: list, format: Optional[Dict] = None) -> Dict:
        """Make a call to the remote LLM API."""
        json_data = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.25,
            "max_tokens": 1024,
            "top_k": 40,
            "top_p": 0.38,
        }

        if format:
            json_data["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "TransactionCheck",
                    "strict": "true",
                    "schema": format,
                },
            }

        try:
            response = requests.post(
                f"{self.api_base_url}/chat/completions",
                headers=self.headers,
                json=json_data,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            logger.error(f"Error calling LLM API: {str(e)}")
            raise