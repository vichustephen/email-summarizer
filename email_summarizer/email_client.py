import imaplib
import email
from email.header import decode_header
import json
import re
from bs4 import BeautifulSoup
import os
from datetime import datetime, timedelta, date
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
from loguru import logger
from typing import List, Dict, Optional

class EmailClient:
    def __init__(self):
        self.imap_server = os.getenv('IMAP_SERVER', 'imap.gmail.com')
        self.imap_port = int(os.getenv('IMAP_PORT', 993))
        self.email_address = os.getenv('EMAIL_ADDRESS')
        self.use_oauth = os.getenv('OAUTH_ENABLED', False) == 'True'
        self.connection = None
        self.token_path = 'token.pickle'
        self.scopes = ['https://mail.google.com/']
        
        # Email logging configuration
        self.enable_logging = os.getenv('ENABLE_EMAIL_LOGGING', 'False').lower() == 'true'
        self.log_file_path = os.getenv('EMAIL_LOG_PATH', 'fetched_emails_log.jsonl')

    def _get_oauth_credentials(self) -> Credentials:
        """Get or refresh OAuth2 credentials."""
        creds = None
        if os.path.exists(self.token_path):
            with open(self.token_path, 'rb') as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_config({
                    'installed': {
                        'client_id': os.getenv('GOOGLE_CLIENT_ID'),
                        'client_secret': os.getenv('GOOGLE_CLIENT_SECRET'),
                        'redirect_uris': ['urn:ietf:wg:oauth:2.0:oob'],
                        'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                        'token_uri': 'https://oauth2.googleapis.com/token',
                    }
                }, self.scopes)
                creds = flow.run_local_server(port=0)

            with open(self.token_path, 'wb') as token:
                pickle.dump(creds, token)

        return creds

    def connect(self):
        """Connect to the IMAP server using OAuth2."""
        try:
            self.connection = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            logger.info('Trying email connection:')
            if self.use_oauth:
                logger.info('using oauth:')
                creds = self._get_oauth_credentials()
                auth_string = f'user={self.email_address}\1auth=Bearer {creds.token}\1\1'
                self.connection.authenticate('XOAUTH2', lambda x: auth_string)
            else:
                self.connection.login(self.email_address, os.getenv('EMAIL_PASSWORD'))
            logger.info("Successfully connected to email server")
        except Exception as e:
            logger.error(f"Failed to connect to email server: {str(e)}")
            raise

    def disconnect(self):
        """Safely disconnect from the IMAP server."""
        if self.connection:
            try:
                self.connection.logout()
            except:
                pass
            self.connection = None

    def _clean_text(self, text: str) -> str:
        """Clean and prepare text for LLM processing."""
        # Note: EmailClient is expected to provide relatively clean text,
        # but this adds robustness in case of unexpected HTML.
        # Check if the text looks like HTML and strip tags if so
        if '<' in text and '>' in text: # Simple heuristic to check for potential HTML
            try:
                soup = BeautifulSoup(text, 'html.parser')
                text = soup.get_text(separator=' ', strip=True)
            except Exception as e:
                logger.warning(f"Failed to parse HTML in _clean_text: {e}")
        # Remove multiple whitespaces and newlines
        text = re.sub(r'\s+', ' ', text)
        # Remove email signatures and footers (common patterns)
        text = re.sub(r'Best regards,.*$', '', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'Sent from.*$', '', text, flags=re.IGNORECASE | re.DOTALL)
        return text.strip()

    def _decode_email_subject(self, subject: str) -> str:
        """Decode email subject with proper character encoding."""
        decoded_headers = decode_header(subject)
        subject_parts = []
        for content, encoding in decoded_headers:
            if isinstance(content, bytes):
                try:
                    content = content.decode(encoding or 'utf-8')
                except:
                    content = content.decode('utf-8', 'ignore')
            subject_parts.append(str(content))
        return ''.join(subject_parts)

    def _log_email_data(self, email_data: Dict, subject: str):
        """Helper method to log email data to file if logging is enabled."""
        if not self.enable_logging:
            return
            
        try:
            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                json.dump(email_data, f, ensure_ascii=False)
                f.write('\n')
            logger.debug(f"Successfully logged email '{subject}' to {self.log_file_path}")
        except Exception as e:
            logger.error(f"Error writing email data to log: {str(e)}")

    def get_emails(self, batch_size: int = 10, days_back: int = 0) -> List[Dict]:
        """Fetch recent emails (both read and unread) from the last N days."""
        if not self.connection:
            self.connect()

        try:
            # Select the inbox mailbox. This is where emails are typically received.
            status, data = self.connection.select('INBOX')
            if status != 'OK':
                raise imaplib.IMAP4.error(f"Failed to select INBOX: {data}")

            # Calculate the date range
            date = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")
            search_criterion = f'(SINCE "{date}")'
            
            _, message_numbers = self.connection.search(None, search_criterion)
            email_list = []
            
            # Process emails in reverse order (newest first)
            message_nums = message_numbers[0].split()[::-1]
            for num in message_nums[:batch_size]:
                _, msg_data = self.connection.fetch(num, '(RFC822)')
                email_body = msg_data[0][1]
                email_message = email.message_from_bytes(email_body)
                
                subject = self._decode_email_subject(email_message['subject'] or '')
                sender = email.utils.parseaddr(email_message['from'])[1]
                date_str = email_message['date']
                date = email.utils.parsedate_to_datetime(date_str)
                logger.info('Email:',email_message['X-Google-Class'])
                # Filter out social email senders
                social_senders = ["facebookmail.com", "linkedin.com", "redditmail.com", "instagram.com", "twitter.com",
                                  "store-news@amazon.in", "marketing"]
                if any(social_sender in sender for social_sender in social_senders):
                    logger.info(f"Skipping email from social sender: {sender}")
                    continue

                # Skip Google Social Classifications, if present
                if 'X-Google-Class' in email_message and 'social' in email_message['X-Google-Class']:
                    logger.info(f"Skipping email with X-Google-Class: social, Subject: {subject}")
                    continue
                body = ""
                if email_message.is_multipart():
                    for part in email_message.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode()
                            break
                        elif part.get_content_type() == "text/html":
                            body = self._clean_text(part.get_payload(decode=True).decode())
                            break
                else:
                    body = email_message.get_payload(decode=True).decode()
                
                email_data = {
                    'id': email_message['message-id'],
                    'subject': subject,
                    'sender': sender,
                    'date': date.isoformat(),  # Convert datetime object to ISO 8601 string for JSON serialization
                    'body': body
                }
                email_list.append(email_data)                # Log the email data if enabled
                self._log_email_data(email_data, subject)
            #print(email_list)
            return email_list
        except Exception as e:
            logger.error(f"Error fetching emails: {str(e)}")
            raise
        finally:
            self.disconnect() 

    def get_emails_for_date(self, target_date: date) -> List[Dict]:
        """
        Fetch emails for a specific date.
        
        Args:
            target_date (date): The date to fetch emails for
            
        Returns:
            List[Dict]: List of email dictionaries with keys: id, subject, sender, date, body
        """
        if not self.connection:
            self.connect()

        try:
            # Select the inbox mailbox
            status, data = self.connection.select('INBOX')
            if status != 'OK':
                raise imaplib.IMAP4.error(f"Failed to select INBOX: {data}")

            # Format the date for IMAP search
            search_date = target_date.strftime("%d-%b-%Y")
            # Search for emails on the specific date
            search_criterion = f'(ON "{search_date}")'
            
            _, message_numbers = self.connection.search(None, search_criterion)
            email_list = []
            
            # Process emails in reverse order (newest first)
            message_nums = message_numbers[0].split()[::-1]
            for num in message_nums:
                _, msg_data = self.connection.fetch(num, '(RFC822)')
                email_body = msg_data[0][1]
                email_message = email.message_from_bytes(email_body)
                
                subject = self._decode_email_subject(email_message['subject'] or '')
                sender = email.utils.parseaddr(email_message['from'])[1]
                date_str = email_message['date']
                email_date = email.utils.parsedate_to_datetime(date_str)

                # Skip social emails and marketing
                social_senders = ["facebookmail.com", "linkedin.com", "redditmail.com", "instagram.com", "twitter.com",
                                "store-news@amazon.in", "marketing"]
                if any(social_sender in sender for social_sender in social_senders):
                    logger.info(f"Skipping email from social sender: {sender}")
                    continue

                # Skip Google Social Classifications
                if 'X-Google-Class' in email_message and 'social' in email_message['X-Google-Class']:
                    logger.info(f"Skipping email with X-Google-Class: social, Subject: {subject}")
                    continue

                # Extract body
                body = ""
                if email_message.is_multipart():
                    for part in email_message.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode()
                            break
                        elif part.get_content_type() == "text/html":
                            body = self._clean_text(part.get_payload(decode=True).decode())
                            break
                else:
                    body = email_message.get_payload(decode=True).decode()
                
                email_data = {
                    'id': email_message['message-id'],
                    'subject': subject,
                    'sender': sender,
                    'date': email_date.isoformat(),
                    'body': body
                }
                email_list.append(email_data)
                
                # Log the email data if enabled
                self._log_email_data(email_data, subject)

            return email_list
        except Exception as e:
            logger.error(f"Error fetching emails for date {target_date}: {str(e)}")
            raise
        finally:
            self.disconnect()