import spacy

# Load the English language model
nlp = spacy.load("en_core_web_sm")

def is_bank_transaction(text):
    """
    Detects if a given text is likely a bank transaction notification.
    (Existing function - kept for context)
    Args:
        text (str): The input text.

    Returns:
        bool: True if the text is likely a bank transaction, False otherwise.
    """
    doc = nlp(text.lower())

    # Keywords commonly found in bank transaction notifications
    transaction_keywords = ["transaction", "payment", "transfer", "debit", "credit", "withdrawal", "deposit",
        "amount", "paid", "received", "sent", "charged", "spent", ]

    # Check for the presence of keywords
    for token in doc:
        if token.lemma_ in transaction_keywords:
            return True

    # Additional checks (optional, can be refined)
    # Look for patterns like currency symbols followed by numbers
    # for token in doc:
    #     if token.is_currency and token.i + 1 < len(doc) and doc[token.i + 1].is_digit:
    #         return True

    return False

def is_positive_transaction(text: str) -> bool:
    """
    Detects if a given text represents a positive financial transaction.
    A positive transaction means it is processed (e.g., successful, completed, credited, debited, paid, received)
    and not failed, pending, or cancelled.

    Args:
        text (str): The input text.

    Returns:
        bool: True if the text likely represents a positive transaction, False otherwise.
    """
    doc = nlp(text.lower())
    text_lower = text.lower() # For multi-word phrase checking

    # Keywords indicating a financial activity
    financial_keywords = {
        "transaction", "payment", "transfer", "debit", "credit", "withdrawal", "deposit",
        "amount", "paid", "received", "sent", "charged", "spent", "refunded", "settled",
        "purchase", "sale", "invoice", "bill", "fee", "charge", "salary", "funds"
    }

    # Keywords indicating a processed or successful state.
    # These imply the transaction has completed and resulted in a credit/debit.
    processed_keywords = {
        "successful", "completed", "processed", "confirmed", "credited", "debited",
        "executed", "approved", "cleared", "settled", "done", "paid", "received",
        "deposited", "withdrawn"
    }

    # Keywords indicating a non-processed, failed, or pending state
    non_processed_keywords = {
        "failed", "failure", "unsuccessful", "declined", "cancelled", "reversed", "pending",
        "scheduled", "upcoming", "attempted", "error", "issue", "rejected", "voided",
        "processing", # "processing" (verb form) often means not yet completed
        "due" # e.g. "payment due"
    }
    
    # Multi-word phrases indicating non-processed state
    multi_word_non_processed = [
        "on hold", "payment due", "will be processed", "yet to be processed",
        "could not be completed", "not completed", "not successful", "unable to complete",
        "unable to process", "did not complete", "was not processed"
    ]

    for phrase in multi_word_non_processed:
        if phrase in text_lower:
            return False # Early exit if a known non-processed phrase is found

    has_financial_indicator = True # testing for now
    is_confirmed_processed = False
    is_explicitly_not_processed = False

    # Check for currency and numbers as a financial indicator
    # found_currency_amount_pattern = False
    # for token in doc:
    #     if token.is_currency:
    #         # Check next token or neighbors for a number
    #         if token.i + 1 < len(doc) and (doc[token.i + 1].is_digit or doc[token.i + 1].like_num):
    #             found_currency_amount_pattern = True
    #             break
    #         # Check previous token if currency symbol is at the end (e.g., 100$)
    #         if token.i - 1 >= 0 and (doc[token.i - 1].is_digit or doc[token.i - 1].like_num):
    #             found_currency_amount_pattern = True
    #             break
    
    # if found_currency_amount_pattern:
    #     has_financial_indicator = True

    for token in doc:
        term = token.lemma_ if token.lemma_ not in ["-pron-"] else token.text # spaCy uses -PRON- for pronouns
        #print('term',term,'text',token.text)

        if term in financial_keywords:
            has_financial_indicator = True
        
        if token.text in processed_keywords: # Use lemmatized term
            is_confirmed_processed = True
        
        if token.text in non_processed_keywords: # Use lemmatized term
            is_explicitly_not_processed = True
            # If a strong non-processed keyword is found, we can mark it.
            # The final decision will check this flag.

    # If any explicitly non-processed keyword is found, it's not a positive transaction.
    if is_explicitly_not_processed:
        return False

    # A positive transaction must:
    # 1. Have a financial indicator.
    # 2. Be confirmed as processed (e.g., "credited", "debited", "successful", "paid", "received").
    # 3. Not be explicitly marked as non-processed (already handled by the check above).
    if has_financial_indicator and is_confirmed_processed:
        return True
        
    return False


# Example texts for is_bank_transaction (existing)
text1 = "Your account has been debited with $50.00 for a recent transaction."
text2 = "Meeting scheduled for tomorrow at 10 AM."
text3 = "You received a payment of £150.00."
text4 = "This is a test email."
text5 = "A transfer of 200 EUR was made from your account."

# Example texts for is_positive_transaction (new)
positive_texts = [
    "HDFC BANK Dear Customer, Rs.67.53 has been debited from your HDFC Bank RuPay Credit Card XX123 to APOLLO PHARMACY on 03-06-25. Your UPI transaction reference number is 438453534. If you did not authorize this transaction,   © HDFC Bank",
    "You received a payment of £150.00.",
    # "A transfer of 200 EUR was made from your account.",
    # "Transaction successful: INR 1000 credited to your account.",
    # "Payment of $25.50 to Merchant X has been completed.",
    # "Your salary of $2000 has been credited.",
    # "Successfully paid $10 for services.",
    # "Funds amounting to 500 USD were deposited into your account.",
    # "Your refund of $30 has been processed."
]

non_positive_texts = [
    "Meeting scheduled for tomorrow at 10 AM.",
    "This is a test email.",
    "Your transaction of $20 has failed.",
    "Payment of Rs. 500 is pending.",
    "Upcoming bill payment of $75 scheduled for next week.",
    "Your request to transfer $100 is currently processing.",
    "Transaction attempt for $99 was unsuccessful.",
    "The payment was cancelled by the user.",
    "Invoice #123 for $200 is due on 2024-12-31.",
    "Your transaction is on hold pending verification.",
    "Your payment of $50 could not be completed successfully at this time."
]

if __name__ == "__main__":
    print("--- Testing is_bank_transaction (existing) ---")
    print(f"'{text1}' is a bank transaction: {is_bank_transaction(text1)}")
    print(f"'{text2}' is a bank transaction: {is_bank_transaction(text2)}")
    print(f"'{text3}' is a bank transaction: {is_bank_transaction(text3)}")
    print(f"'{text4}' is a bank transaction: {is_bank_transaction(text4)}")
    print(f"'{text5}' is a bank transaction: {is_bank_transaction(text5)}")

    print("\n--- Testing is_positive_transaction (new) ---")
    print("\nExpected POSITIVE transactions:")
    for i, pt_text in enumerate(positive_texts):
        print(f"Test {i+1}: '{pt_text}' -> Positive? {is_positive_transaction(pt_text)}")

    print("\nExpected NON-POSITIVE transactions:")
    for i, npt_text in enumerate(non_positive_texts):
        print(f"Test {i+1}: '{npt_text}' -> Positive? {is_positive_transaction(npt_text)}")

# (Inside is_positive_transaction function, after nlp(text.lower()))
# from spacy.matcher import Matcher
# matcher = Matcher(nlp.vocab)

# # Pattern: auxiliary verb + "not" + verb + (optional adverb "successfully")
# pattern_neg_completion = [
#     {"POS": "AUX"}, # e.g., could, did, was
#     {"LOWER": "not"},
#     {"POS": "VERB"}, # e.g., complete, process, execute
#     {"LOWER": "successfully", "OP": "?"} # Optional: "successfully"
# ]
# matcher.add("NEG_COMPLETION", [pattern_neg_completion])

# matches = matcher(doc)
# if matches:
#     # This indicates a more complex negative pattern was found
#     is_explicitly_not_processed = True
#     # Potentially return False directly here if such a match is a strong negative signal
