from pydantic import BaseModel


class FinancialTransaction(BaseModel):
    """
    Represents a financial transaction.
    """
    amount: float
    type: str
    vendor: str
    date: str
    ref: str
    category: str