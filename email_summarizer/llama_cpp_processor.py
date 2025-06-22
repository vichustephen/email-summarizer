import json
import os
from typing import Dict, List, Optional
from loguru import logger
import re
from llama_cpp import Llama
from email_summarizer.text_utils import is_bank_transaction, is_positive_transaction

try:
    from .models.transaction import FinancialTransaction
    from .models.transactionCheck import TransactionCheck
    from .database import Transaction, get_session
except ImportError:
    from models.transaction import FinancialTransaction
    from models.transactionCheck import TransactionCheck

class LlamaCppProcessor:
    def __init__(self):
        self.model_path = os.getenv('LLAMA_MODEL_PATH')
        if not self.model_path:
            raise ValueError("LLAMA_MODEL_PATH environment variable is required")
        
        self.llm = Llama(
            model_path=self.model_path,
            n_ctx=int(os.getenv('LLAMA_N_CTX', 2048)),
            n_threads=int(os.getenv('LLAMA_N_THREADS', 8)),
            n_gpu_layers=int(os.getenv('LLAMA_N_GPU_LAYERS', 0))
        )

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
        prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        
        response = self.llm(
            prompt,
            max_tokens=1024,
            temperature=0.25,
            top_k=40,
            top_p=0.38,
            stop=["\n"],
            echo=False
        )
        
        return response

    def _extract_json_from_response(self, response: Dict, model_class: type) -> Optional[Dict]:
        try:
            if not response.get('choices'):
                logger.warning("No 'choices' in LLM response.")
                return None
            
            content = response['choices'][0]['text']
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
        try:
            messages = [
                {"role": "system", "content": self.summarization_system_prompt},
                {"role": "user", "content": email_body}
            ]
            
            response_data = self._call_llm_api(messages)
            
            if response_data and response_data.get('choices') and \
               len(response_data['choices']) > 0 and \
               response_data['choices'][0].get('text'):
                
                summary = response_data['choices'][0]['text']
                summary = re.sub(r'<think>.*?</think>', '', summary, flags=re.DOTALL).strip()
                logger.debug(f"Successfully summarized content. Summary length: {len(summary)}")
                return summary
            else:
                logger.warning("LLM response for summarization was empty or malformed.")
                return ""
        except Exception as e:
            logger.error(f"Error during email summarization: {str(e)}")
            return ""

    def process_email(self, subject: str, content: str) -> Dict:
        default_response = {"amount": 0.0}
        try:
            logger.info("Summarizing email content...")
            summary = self.summarize_email_content(content)
            
            effective_body_content: str
            if summary and summary.strip():
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
        try:
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
                return result.get('is_transaction', False)
            return False
            
        except Exception as e:
            logger.error(f"Error in transaction detection: {str(e)}")
            return True

    def process_emails(self, emails: List[Dict], status_callback=None) -> List[Dict]:
        transactions = []
        session = get_session()
        
        if status_callback:
            status_callback(total=len(emails), processed=0, message="Starting email processing")
        
        for i, email in enumerate(emails, 1):
            try:
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
                
                result = self.process_email(email['subject'], email['body'])
                
                if result['amount'] > 0:
                    result['email_id'] = email['id']
                    transactions.append(result)
                    logger.info(f"Extracted transaction: {result['vendor']} - {result['amount']} {result['type']}")
                
            except Exception as e:
                logger.error(f"Error processing email {email['id']}: {str(e)}")
                continue
        
        if status_callback:
            status_callback(message="Email processing complete")
        
        return transactions
