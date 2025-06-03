from pydantic import BaseModel


class TransactionCheck(BaseModel):
    """
    Represents the result of a transaction check,
    including a boolean indicating if it's a transaction
    and a confidence score.
    """
    is_transaction: bool
    confidence: float