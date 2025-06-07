import spacy

# Load the English language model
nlp = spacy.load("en_core_web_sm")

def is_bank_transaction(text):
    """
    Detects if a given text is likely a bank transaction notification.

    Args:
        text (str): The input text.

    Returns:
        bool: True if the text is likely a bank transaction, False otherwise.
    """
    doc = nlp(text.lower())

    # Keywords commonly found in bank transaction notifications
    transaction_keywords = ["transaction", "payment", "transfer", "debit", "credit", "amount", "paid", "received", "account", "balance"]

    # Check for the presence of keywords
    for token in doc:
        if token.text in transaction_keywords:
            return True

    # Additional checks (optional, can be refined)
    # Look for patterns like currency symbols followed by numbers
    for token in doc:
        if token.is_currency and token.nbor().is_digit:
            return True

    return False

# Example texts
text1 = "Your account has been debited with $50.00 for a recent transaction."
text2 = "Meeting scheduled for tomorrow at 10 AM."
text3 = "You received a payment of £150.00."
text4 = "This is a test email."
text5 = "A transfer of 200 EUR was made from your account."

print(f"'{text1}' is a bank transaction: {is_bank_transaction(text1)}")
print(f"'{text2}' is a bank transaction: {is_bank_transaction(text2)}")
print(f"'{text3}' is a bank transaction: {is_bank_transaction(text3)}")
print(f"'{text4}' is a bank transaction: {is_bank_transaction(text4)}")
print(f"'{text5}' is a bank transaction: {is_bank_transaction(text5)}")
