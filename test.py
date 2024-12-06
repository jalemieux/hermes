# run.py

from datetime import datetime
import logging
from app import create_app
from app.mailbox_accessor import MailboxAccessor
from app.models import Summary, User, db
from app.summary_generator import SummaryGenerator, test_fetch_emails, test_process_emails, test_synthesize_newsletter
from config import Config


app = create_app()

logging.basicConfig(level=logging.INFO)

if __name__ == '__main__':
    #app.run(debug=True)
    with app.app_context():
         summary_generator = SummaryGenerator()
         new_summary = Summary.query.first()

         summary_generator.generate_summary(1,new_summary )   
         
         #test_synthesize_newsletter(summary_generator)
