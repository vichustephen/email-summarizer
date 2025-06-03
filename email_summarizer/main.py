import os
import time
import schedule
from datetime import datetime, timedelta
from dotenv import load_dotenv
from loguru import logger
from database import Transaction
import sys

from email_client import EmailClient
from llm_processor import LLMProcessor
from database import get_session, add_transaction, get_daily_transactions
from notifier import EmailNotifier

# Configure logging
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=os.getenv("LOG_LEVEL", "INFO")
)
logger.add(
    os.getenv("LOG_FILE", "email_summarizer.log"),
    rotation="1 day",
    retention="7 days",
    level=os.getenv("LOG_LEVEL", "INFO")
)

def process_emails():
    """Main function to process emails and extract transactions."""
    try:
        logger.info("Starting email processing")
        
        # Initialize components
        email_client = EmailClient()
        llm_processor = LLMProcessor()
        session = get_session()
        
        # Get recent emails
        batch_size = int(os.getenv('BATCH_SIZE', 20))
        days_back = int(os.getenv('DAYS_BACK', 0))
        emails = email_client.get_emails(batch_size=batch_size, days_back=days_back)
        
        if not emails:
            logger.info("No emails to process")
            return
        
        logger.info(f"Processing {len(emails)} emails")
        
        # Process each email
        for email in emails:
            try:
                # Check if email was already processed
                if session.query(Transaction).filter_by(email_id=email['id']).first():
                    logger.debug(f"Skipping already processed email: {email['subject']}")
                    continue
                
                # Pre-filter emails using LLM
                if not llm_processor.is_potential_transaction(email['subject'], email['sender']):
                    logger.debug(f"Skipping non-transaction email: {email['subject']}")
                    continue
                
                # Process with LLM
                result = llm_processor.process_email(email['subject'], email['body'])
                
                if result['is_transaction']:
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
        
    except Exception as e:
        logger.error(f"Error in process_emails: {str(e)}")

def send_daily_summary():
    """Generate and send daily transaction summary."""
    try:
        logger.info("Preparing daily summary")
        
        # Get yesterday's transactions
        yesterday = datetime.now().date() - timedelta(days=1)
        session = get_session()
        transactions = get_daily_transactions(session, yesterday)
        
        if transactions:
            # Send summary email
            notifier = EmailNotifier()
            notifier.send_daily_summary(transactions, yesterday)
            logger.info("Daily summary sent successfully")
        else:
            logger.info("No transactions to summarize")
        
        session.close()
        
    except Exception as e:
        logger.error(f"Error in send_daily_summary: {str(e)}")

def main():
    """Main entry point for the email summarizer agent."""
    # Load environment variables
    load_dotenv(override=True)
    
    # Schedule tasks
    processing_interval = int(os.getenv('PROCESSING_INTERVAL_HOURS', 4))
    summary_time = os.getenv('SUMMARY_TIME', '23:00')
    
    # Schedule email processing
    schedule.every(processing_interval).hours.do(process_emails)
    
    # Schedule daily summary
    schedule.every().day.at(summary_time).do(send_daily_summary)
    
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