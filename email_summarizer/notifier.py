import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from typing import Dict, List
from datetime import datetime
from loguru import logger
try:
    # When imported as a module
    from . import database
except ImportError as e:
    # When run as a script
    print('error on import',str(e))
    import database

class EmailNotifier:
    def __init__(self):
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.email_address = os.getenv('EMAIL_ADDRESS')
        self.notification_email = os.getenv('NOTIFICATION_EMAIL')
        self.password = os.getenv('EMAIL_PASSWORD')
        self.db_session = database.get_session()

    def _format_currency(self, amount: float, currency: str) -> str:
        """Format currency amount with proper symbol."""
        # currency_symbols = {
        #     'USD': '$',
        #     'EUR': '€',
        #     'GBP': '£',
        #     'JPY': '¥'
        # }
        # symbol = currency_symbols.get(currency, currency)
        # return f"{symbol}{amount:,.2f}"
        return f"{amount:,.2f}"

    def _generate_summary_text(self, transactions: List[Dict], total_amount: Dict[str, float]) -> str:
        """Generate plain text summary for storage."""
        summary = []
        
        # Add total amount
        summary.append("Total Spending:")
        for currency, amount in total_amount.items():
            #summary.append(f"{self._format_currency(amount, currency)} {currency}")
            summary.append(f"{amount}")
        
        # Group by category
        categories: Dict[str, List[Dict]] = {}
        for transaction in transactions:
            category = transaction['category']
            if category not in categories:
                categories[category] = []
            categories[category].append(transaction)
        
        # Add category summaries
        for category, cat_transactions in categories.items():
            summary.append(f"\n{category}:")
            for trans in cat_transactions:
                #amount = self._format_currency(trans['amount'], trans['currency'])
                amount = trans['amount']
                summary.append(f"- {trans['vendor']}: {amount}")
        
        return "\n".join(summary)

    def _generate_summary_html(self, transactions: List[Dict], date: datetime) -> str:
        """Generate HTML content for the daily summary email."""
        # Group transactions by category
        categories: Dict[str, List[Dict]] = {}
        total_amount: Dict[str, float] = {}
        
        for transaction in transactions:
            category = transaction['category']
            #currency = transaction['currency']
            
            if category not in categories:
                categories[category] = []
            categories[category].append(transaction)
            
            # if currency not in total_amount:
            #     total_amount[currency] = 0
            if 'amount' not in total_amount:
                total_amount['amount'] = 0
            total_amount['amount'] += transaction['amount']

        # Store daily summary in database
        summary_text = self._generate_summary_text(transactions, total_amount)
        total_sum = sum(amount for amount in total_amount.values())
        
        database.add_daily_summary(
            self.db_session,
            date=date,
            total_amount=total_sum,
            transaction_count=len(transactions),
            summary_text=summary_text
        )

        # Generate HTML content
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; }}
                .category {{ margin-top: 20px; }}
                .transaction {{ margin: 10px 0; padding: 10px; background-color: #fff; border: 1px solid #ddd; border-radius: 5px; }}
                .total {{ margin-top: 20px; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>Daily Transaction Summary</h2>
                    <p>Date: {date.strftime('%B %d, %Y')}</p>
                </div>
        """

        # Add total amount section
        html += "<div class='total'><h3>Total Spending:</h3>"
        for currency, amount in total_amount.items():
            #html += f"<p>{self._format_currency(amount, currency)} {currency}</p>"
            html += f"<p>{amount}</p>"
        html += "</div>"

        # Add transactions by category
        for category, cat_transactions in categories.items():
            html += f"""
                <div class="category">
                    <h3>{category}</h3>
            """
            
            for trans in cat_transactions:
                #formatted_amount = self._format_currency(trans['amount'], trans['currency'])
                formatted_amount = trans['amount']
                html += f"""
                    <div class="transaction">
                        <p><strong>{trans['vendor']}</strong> - {formatted_amount}</p>
                    </div>
                """
            
            html += "</div>"

        html += """
            </div>
        </body>
        </html>
        """
        
        return html

    def send_daily_summary(self, transactions: List[Dict], date: datetime):
        """Send daily transaction summary email."""
        if not transactions:
            logger.info("No transactions to summarize")
            return

        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f'Daily Transaction Summary - {date.strftime("%B %d, %Y")}'
            msg['From'] = self.email_address
            msg['To'] = self.notification_email

            html_content = self._generate_summary_html(transactions, date)
            msg.attach(MIMEText(html_content, 'html'))

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_address, self.password)
                server.send_message(msg)

            logger.info("Daily summary email sent successfully")
            
        except Exception as e:
            logger.error(f"Failed to send daily summary email: {str(e)}")
            raise 