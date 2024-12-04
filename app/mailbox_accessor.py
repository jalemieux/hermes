import logging
import mailslurp_client
from datetime import datetime, timedelta

class MailboxAccessor:
    def __init__(self, api_key, inbox_id):
        # Configure the MailSlurp client with the provided API key
        configuration = mailslurp_client.Configuration()
        configuration.api_key['x-api-key'] = api_key
        self.api_client = mailslurp_client.ApiClient(configuration)
        self.inbox_id = inbox_id

    def get_emails_from_last_n_days(self, n):
        since_date = datetime.now() - timedelta(days=n)
        since_date_iso = since_date.isoformat() + 'Z'

        with self.api_client as api_client:
            inbox_controller = mailslurp_client.InboxControllerApi(api_client)
            email_controller = mailslurp_client.EmailControllerApi(api_client)
            logging.debug(f"Fetched inbox {inbox_controller.get_inbox(self.inbox_id)} look for emails since {since_date_iso}")
            emails_overview = inbox_controller.get_inbox_emails_paginated(
                inbox_id=self.inbox_id,
                since=since_date_iso,
                sort='ASC'
            )

            # Fetch full email content for each email
            full_emails = []
            for email_overview in emails_overview.content:
                logging.debug(f"Fetching full email content for email {email_overview.id}")
                full_email = email_controller.get_email(email_overview.id)
                full_emails.append(full_email)
                
            return full_emails 