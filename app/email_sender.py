from flask import current_app
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class EmailSender:
    def __init__(self):
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.sender_email = current_app.config['GMAIL_SENDER_EMAIL']
        self.sender_password = current_app.config['GMAIL_APP_PASSWORD']

    def send_email(self, to_email: str, subject: str, body: str):
        """Send an email using Gmail SMTP"""
        message = MIMEMultipart()
        message["From"] = self.sender_email
        message["To"] = to_email
        message["Subject"] = subject

        # Add body to email
        message.attach(MIMEText(body, "plain"))

        try:
            # Create SMTP session
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            
            # Login to sender email
            server.login(self.sender_email, self.sender_password)
            
            # Send email
            server.send_message(message)
            server.quit()
            return True
        except Exception as e:
            current_app.logger.error(f"Failed to send email: {str(e)}")
            raise e 