import os
import time
import schedule
from datetime import datetime, timedelta, date
from dotenv import load_dotenv
from loguru import logger
import sys
from typing import Optional
import threading

try:
    # When imported as a module
    from . import database
    from . import email_client
    from . import llm_processor
    from . import notifier
    from .database import Transaction, get_session, add_transaction, get_daily_transactions
    from .email_client import EmailClient
    from .llm_processor import LLMProcessor
    from .notifier import EmailNotifier
except ImportError as e:
    # When run as a script
    print('errored on import',str(e))
    from database import Transaction, get_session, add_transaction, get_daily_transactions
    from email_client import EmailClient
    from llm_processor import LLMProcessor
    from notifier import EmailNotifier

#pipeline-> is transaction -> is not otp or something -> is positive transaction , try spacy for credited /
#try positive classification using BERT -> unlikely
#After LLM extracts find properly credited or debited -> try pattern matching
# Configure logging
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=os.getenv("LOG_LEVEL", "INFO")
)
logger.add(
    os.getenv("LOG_FILE", "logs/email_summarizer.log"),
    rotation="1 day",
    retention="7 days",
    level=os.getenv("LOG_LEVEL", "INFO")
)

# Global state
running = False
last_run = None
next_run = None
stop_event = threading.Event()
current_batch = {
    'total_emails': 0,
    'processed': 0,
    'current_email': '',
    'processing_message': 'Idle'
}

def update_processing_status(total=None, processed=None, current=None, message=None):
    """Update the current processing status."""
    global current_batch
    if total is not None:
        current_batch['total_emails'] = total
    if processed is not None:
        current_batch['processed'] = processed
    if current is not None:
        current_batch['current_email'] = current
    if message is not None:
        current_batch['processing_message'] = message

def get_processing_status():
    """Get the current processing status."""
    return current_batch

def process_date_range(start_date: date, end_date: date, notify_user: bool = True):
    """Process emails and generate summaries for a date range."""
    logger.info(f"Processing date range: {start_date} to {end_date}, notify_user={notify_user}")
    update_processing_status(message=f"Processing emails from {start_date} to {end_date}")
    
    try:
        client = EmailClient()
        processor = LLMProcessor()
        
        current_date = start_date
        while current_date <= end_date:
            if stop_event.is_set():
                update_processing_status(message="Processing stopped")
                return
                
            logger.info(f"Processing date: {current_date}")
            update_processing_status(message=f"Fetching emails for {current_date}")
            
            # Get emails for the day
            emails = client.get_emails_for_date(current_date)
            if not emails:
                logger.info(f"No emails found for {current_date}")
                current_date += timedelta(days=1)
                continue
            
            # Process emails with status updates
            transactions = processor.process_emails(
                emails,
                status_callback=lambda **kwargs: update_processing_status(**{
                    **kwargs,
                    'message': kwargs.get('message', '') + f" for {current_date}"
                })
            )
            
            if transactions and notify_user:
                # Generate and store daily summary
                notifier = EmailNotifier()
                notifier.send_daily_summary(transactions, current_date)
            elif transactions:
                logger.info(f"Transactions found for {current_date}, but notification is disabled.")
            else:
                logger.info(f"No transactions found for {current_date}")

            current_date += timedelta(days=1)
        
        update_processing_status(message="Processing complete",processed=current_batch['total_emails'])
        
    except Exception as e:
        logger.error(f"Error in process_date_range: {str(e)}")
        update_processing_status(message=f"Error: {str(e)}")
        raise

def process_current_day_emails():
    """Process emails for the current day."""
    global last_run
    from .api import notify_user_global
    try:
        today = date.today()
        process_date_range(today, today, notify_user=notify_user_global)
        last_run = datetime.now()
        logger.info("Successfully processed current day emails")
    except Exception as e:
        logger.error(f"Error processing current day emails: {e}")
        raise

def start_summarizer():
    """Start the email summarizer service."""
    global running, stop_event
    
    if running:
        logger.warning("Summarizer is already running")
        return
    
    try:
        running = True
        stop_event.clear()
        
        # Process emails immediately
        process_current_day_emails()
        
        # Run continuously until stopped
        while not stop_event.is_set():
            schedule.run_pending()
            time.sleep(1)
            
    except Exception as e:
        logger.error(f"Error in start_summarizer: {e}")
        running = False
        raise

def stop_summarizer():
    """Stop the email summarizer service."""
    global running, stop_event
    
    if not running:
        logger.warning("Summarizer is not running")
        return
    
    stop_event.set()
    running = False
    logger.info("Summarizer stopped")

def configure_schedule(interval_minutes: int = 30, start_time: Optional[str] = None, end_time: Optional[str] = None):
    """Configure the summarizer schedule."""
    # Clear existing schedule
    schedule.clear()
    
    # Schedule the job
    schedule.every(interval_minutes).minutes.do(process_current_day_emails)
    
    if start_time:
        schedule.every().day.at(start_time).do(process_current_day_emails)
    if end_time:
        schedule.every().day.at(end_time).do(stop_summarizer)
    
    logger.info(f"Schedule configured: every {interval_minutes} minutes")
    
    # Update next run time
    global next_run
    next_run = schedule.next_run()

def get_last_run_time():
    """Get the last run time as ISO string."""
    return last_run.isoformat() if last_run else None

def get_next_run_time():
    """Get the next scheduled run time as ISO string."""
    return next_run.isoformat() if next_run else None

def is_running():
    """Check if the summarizer is running."""
    return running

def process_emails():
    """Main function to process emails and extract transactions."""
    try:
        logger.info("Starting email processing")
        update_processing_status(message="Initializing email processing...")
        
        # Initialize components
        email_client = EmailClient()
        llm_processor = LLMProcessor()
        session = get_session()
        
        # Get recent emails
        batch_size = int(os.getenv('BATCH_SIZE', 20))
        days_back = int(os.getenv('DAYS_BACK', 0))
        update_processing_status(message="Fetching emails...")
        emails = email_client.get_emails(batch_size=batch_size, days_back=days_back)
        
        if not emails:
            logger.info("No emails to process")
            update_processing_status(message="No emails to process")
            return
        
        logger.info(f"Processing {len(emails)} emails")
        update_processing_status(total=len(emails), processed=0, message="Processing emails...")
        
        for i, email in enumerate(emails, 1):
            try:
                update_processing_status(
                    processed=i,
                    current=email['subject'],
                    message=f"Processing email {i} of {len(emails)}"
                )
                
                # Hmm.... check if email was already processed
                if session.query(Transaction).filter_by(email_id=email['id']).first():
                    logger.debug(f"Skipping already processed email: {email['subject']}")
                    continue
                
                # Pre-filter emails using LLM, but don't filter out emails with 'bank' in sender or subject
                if 'bank' not in email['subject'].lower() and 'bank' not in email['sender'].lower():
                # Uncomment this line if we want a LLM to verify using the subject
                # if not llm_processor.is_potential_transaction(email['subject'], email['sender']):
                    logger.debug(f"Skipping non-transaction email: {email['subject']}")
                    continue
                
                # Process with LLM
                result = llm_processor.process_email(email['subject'], email['body'])
                
                if result['amount'] > 0:
                    # Add to database
                    add_transaction(
                        session,
                        email_id=email['id'],
                        date=datetime.strptime(result['date'], '%Y-%m-%d').date(),
                        vendor=result['vendor'],
                        amount=result['amount'],
                        type=result['type'],
                        category=result['category'],
                        ref=result['ref']
                    )
                    logger.info(f"Added transaction: {result['vendor']} - {result['amount']} {result['type']}")
                
            except Exception as e:
                logger.error(f"Error processing email {email['id']}: {str(e)}")
                continue
        
        session.close()
        logger.info("Completed email processing")
        update_processing_status(message="Processing complete")
        
    except Exception as e:
        logger.error(f"Error in process_emails: {str(e)}")
        update_processing_status(message=f"Error: {str(e)}")

def main():
    """Main entry point for the email summarizer agent."""
    # Load environment variables
    load_dotenv(override=True)
    
    # Schedule tasks
    processing_interval = int(os.getenv('PROCESSING_INTERVAL_HOURS', 4))
    summary_time = os.getenv('SUMMARY_TIME', '23:00')
    
    # Schedule email processing
    schedule.every(processing_interval).hours.do(process_current_day_emails)
    
    # Schedule daily summary
    #TODO schedule.every().day.at(summary_time).do(send_daily_summary)
    
    logger.info("Email Summarizer Agent started")
    logger.info(f"Email processing scheduled every {processing_interval} hours")
    logger.info(f"Daily summary scheduled at {summary_time}")
    
    # Run initial processing
    process_emails()
    
    # Main loop
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("Shutting down Email Summarizer Agent")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {str(e)}")
            time.sleep(300)  # Wait 5 minutes before retrying

if __name__ == "__main__":
    main() 