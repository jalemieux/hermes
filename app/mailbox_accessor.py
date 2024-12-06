import logging
import mailslurp_client
from datetime import datetime, timedelta

from app.models import User
from config import Config

class MailboxAccessor:
    def __init__(self):
        # Configure the MailSlurp client with the provided API key
        configuration = mailslurp_client.Configuration()
        configuration.api_key['x-api-key'] = Config.MAILSLURP_API_KEY
        self.api_client = mailslurp_client.ApiClient(configuration)
        #self.inbox_id = inbox_id

    def get_emails_from_last_n_days(self, inbox_id, n):
        since_date = datetime.now() - timedelta(days=n)
        since_date_iso = since_date.isoformat() + 'Z'

        with self.api_client as api_client:
            inbox_controller = mailslurp_client.InboxControllerApi(api_client)
            email_controller = mailslurp_client.EmailControllerApi(api_client)
            #logging.debug(f"Fetched inbox {inbox_controller.get_inbox(self.inbox_id)} look for emails since {since_date_iso}")
            emails_overview = inbox_controller.get_inbox_emails_paginated(
                inbox_id=inbox_id,
                since=since_date_iso,
                sort='ASC'
            )

            # Fetch full email content for each email
            full_emails = []
            for email_overview in emails_overview.content:
                #logging.debug(f"Fetching full email content for email {email_overview.id}")
                full_email = email_controller.get_email(email_overview.id)
                full_emails.append(full_email)
                
            return full_emails 
    
    def create_forwarder(self, inbox_id, forward_to_email):
        from mailslurp_client.models.create_inbox_forwarder_options import CreateInboxForwarderOptions
        inbox_forwarder_controller = mailslurp_client.InboxForwarderControllerApi(self.api_client)
        return inbox_forwarder_controller.create_new_inbox_forwarder(inbox_id=inbox_id, 
            create_inbox_forwarder_options=CreateInboxForwarderOptions(
                field="SUBJECT",
                match='*',
                forward_to_recipients=[forward_to_email]
            )
        )


    def create_mailbox(self) -> tuple[str, str]:
        with self.api_client as api_client:
            # create an inbox
            inbox_controller = mailslurp_client.InboxControllerApi(api_client)
            inbox = inbox_controller.create_inbox(
                #expires_at = datetime.now() + timedelta(days=10)
            )
            logging.info(f"Created inbox {inbox}")
            #inbox =  {'created_at': datetime.datetime(2024, 12, 4, 0, 30, 45, 251000, tzinfo=tzutc()),
            #  'description': None,
            #  'domain_id': None,
            #  'email_address': '3981e2bb-e8b5-4012-a82f-a6c409a17fc6@mailslurp.biz',
            #  'expires_at': '2024-12-05T12:30:45.242Z',
            #  'favourite': False,
            #  'functions_as': None,
            #  'id': '3981e2bb-e8b5-4012-a82f-a6c409a17fc6',
            #  'inbox_type': 'HTTP_INBOX',
            #  'name': None,
            #  'read_only': False,
            #  'tags': [],
            #  'user_id': '2ffa1a89-3cf2-4542-ac20-9dcb2f33a09c',
            #  'virtual_inbox': False}
        # Add the MailSlurp inbox email_address and id to the user table as MailSlurp attributes
        return inbox.email_address, inbox.id