from flask import Flask
import logging
from app.email_sender import EmailSender
from config import Config

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_send_email():
    # Create a minimal Flask app for context
    app = Flask(__name__)
    app.config.from_object(Config)
    
    with app.app_context():
        try:
            email_sender = EmailSender()
            success = email_sender.send_email(
                to_email="jalemieux@gmail.com",  # Replace with your test email
                subject="Test Email from Hermes",
                body="""
                Hello!
                
                This is a test email from the Hermes password reset system.
                
                If you received this email, the Gmail SMTP configuration is working correctly.
                
                Best regards,
                Hermes Team
                """
            )
            
            if success:
                logger.info("✅ Email sent successfully!")
            
        except Exception as e:
            logger.error(f"❌ Failed to send email: {str(e)}")
            raise e

if __name__ == "__main__":
    test_send_email() 