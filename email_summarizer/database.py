from loguru import logger
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Date, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()

class Transaction(Base):
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True)
    email_id = Column(String, unique=True)
    date = Column(Date, index=True)
    vendor = Column(String)
    amount = Column(Float)
    type = Column(String)
    category = Column(String)
    ref = Column(String)
    processed_at = Column(DateTime, default=datetime.utcnow)

class DailySummary(Base):
    __tablename__ = 'daily_summaries'
    
    id = Column(Integer, primary_key=True)
    date = Column(Date, index=True)  # Removed unique constraint
    total_amount = Column(Float)
    transaction_count = Column(Integer)
    summary_text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    """Initialize the database and create tables."""
    database_url = os.getenv('DATABASE_URL', 'sqlite:///transactions.db')
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    return engine

def get_session():
    """Create a new database session."""
    engine = init_db()
    Session = sessionmaker(bind=engine)
    return Session()

def add_transaction(session, **kwargs):
    """Add a new transaction to the database."""
    transaction = Transaction(**kwargs)
    session.add(transaction)
    session.commit()
    return transaction

def add_daily_summary(session, date, total_amount, transaction_count, summary_text):
    """Add a new daily summary to the database."""
    summary = DailySummary(
        date=date,
        total_amount=total_amount,
        transaction_count=transaction_count,
        summary_text=summary_text
    )
    session.add(summary)
    session.commit()
    return summary

def get_daily_transactions(session, date):
    """Get all transactions for a specific date."""
    return session.query(Transaction).filter(
        Transaction.date == date
    ).all()

def get_transactions_by_date_range(session, start_date, end_date):
    """Get all transactions within a date range."""
    return session.query(Transaction).filter(
        Transaction.date >= start_date,
        Transaction.date <= end_date
    ).order_by(Transaction.date.desc()).all()

def get_daily_summaries(session, start_date, end_date):
    """Get daily summaries within a date range."""
    return session.query(DailySummary).filter(
        DailySummary.date >= start_date,
        DailySummary.date <= end_date
    ).order_by(DailySummary.date.desc()).all()

def get_transactions_by_category(session, start_date, end_date):
    """Get transactions grouped by category within a date range."""
    transactions = get_transactions_by_date_range(session, start_date, end_date)
    categories = {}
    for transaction in transactions:
        if transaction.category not in categories:
            categories[transaction.category] = []
        categories[transaction.category].append(transaction)
    return categories 