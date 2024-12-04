# run.py

import logging
from app import create_app
from app.mailbox_accessor import MailboxAccessor
from app.models import User
from app.summary_generator import SummaryGenerator
from config import Config

app = create_app()

logging.basicConfig(level=logging.DEBUG)

if __name__ == '__main__':
    #app.run(debug=True)
    with app.app_context():
        summary_generator = SummaryGenerator()
        start_date, end_date = summary_generator._get_date_range(1)
        print(start_date, end_date)
        user = User.query.get(1)
        inbox_id = user.mailslurp_inbox_id

        #mailbox = MailboxAccessor(Config.MAILSLURP_API_KEY, inbox_id)

        print(user.id, inbox_id)
        #emails = mailbox.get_emails_from_last_n_days(1)
        #print(len(emails))
        email_ids = summary_generator.fetch_and_process_emails(user.id, inbox_id, start_date, end_date)
        #print(email_ids)