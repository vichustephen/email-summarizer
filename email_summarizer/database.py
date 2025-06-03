from loguru import logger
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()

class Transaction(Base):
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True)
    email_id = Column(String, unique=True)
    date = Column(Date)
    vendor = Column(String)
    amount = Column(Float)
    type = Column(String)
    category = Column(String)
    ref = Column(String)
    processed_at = Column(DateTime, default=datetime.utcnow)

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

def get_daily_transactions(session, date):
    """Get all transactions for a specific date."""
    return session.query(Transaction).filter(
        Transaction.transaction_date == date
    ).all()

def get_transactions_by_category(session, date):
    """Get transactions grouped by category for a specific date."""
    transactions = get_daily_transactions(session, date)
    categories = {}
    for transaction in transactions:
        if transaction.category not in categories:
            categories[transaction.category] = []
        categories[transaction.category].append(transaction)
    return categories 