import imaplib
import email
from email.header import decode_header
from bs4 import BeautifulSoup
import os
from datetime import datetime, timedelta
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
        self.use_oauth = True
        self.connection = None
        self.token_path = 'token.pickle'
        self.scopes = ['https://mail.google.com/']

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
            if self.use_oauth:
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

    def _clean_html(self, html_content: str) -> str:
        """Clean HTML content and extract plain text."""
        soup = BeautifulSoup(html_content, 'html.parser')
        return soup.get_text(separator=' ', strip=True)

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

    def get_emails(self, batch_size: int = 10, days_back: int = 1) -> List[Dict]:
        """Fetch recent emails (both read and unread) from the last N days."""
        if not self.connection:
            self.connect()

        try:
            self.connection.select('INBOX')
            
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
                
                body = ""
                if email_message.is_multipart():
                    for part in email_message.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode()
                            break
                        elif part.get_content_type() == "text/html":
                            body = self._clean_html(part.get_payload(decode=True).decode())
                            break
                else:
                    body = email_message.get_payload(decode=True).decode()
                
                email_list.append({
                    'id': email_message['message-id'],
                    'subject': subject,
                    'sender': sender,
                    'date': date,
                    'body': body
                })
            
            return email_list
        except Exception as e:
            logger.error(f"Error fetching emails: {str(e)}")
            raise
        finally:
            self.disconnect() 