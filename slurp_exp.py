# pip install mailslurp-client
from dataclasses import Field
import pprint
import mailslurp_client
# create a mailslurp configuration
# configuration = mailslurp_client.Configuration()
# configuration.api_key['x-api-key'] = "9f2c4fd3d243e31a0086d86fe8c59019613bc29d952e87c8729ed650b25c755c"
# with mailslurp_client.ApiClient(configuration) as api_client:
#     # create an inbox
#     inbox_controller = mailslurp_client.InboxControllerApi(api_client)
#     inbox = inbox_controller.create_inbox()
#     print(inbox)

# {'created_at': datetime.datetime(2024, 12, 4, 0, 30, 45, 251000, tzinfo=tzutc()),
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
        since_date = datetime.utcnow() - timedelta(days=n)
        since_date_iso = since_date.isoformat() + 'Z'

        with self.api_client as api_client:
            inbox_controller = mailslurp_client.InboxControllerApi(api_client)
            email_controller = mailslurp_client.EmailControllerApi(api_client)
            
            emails_overview = inbox_controller.get_inbox_emails_paginated(
                inbox_id=self.inbox_id,
                since=since_date_iso,
                sort='ASC'
            )

            # Fetch full email content for each email
            full_emails = []
            for email_overview in emails_overview.content:
                full_email = email_controller.get_email(email_overview.id)
                full_emails.append(full_email)
                
            return full_emails

# Replace with your MailSlurp API key and the target inbox ID
api_key = '9f2c4fd3d243e31a0086d86fe8c59019613bc29d952e87c8729ed650b25c755c'
inbox_id = '3981e2bb-e8b5-4012-a82f-a6c409a17fc6'

# Create an instance of MailboxAccessor
mailbox_accessor = MailboxAccessor(api_key, inbox_id)

# Retrieve emails from the last 7 days
emails = mailbox_accessor.get_emails_from_last_n_days(1)

# Process the retrieved emails with full content
# for email in emails:
#     print(f"Subject: {email.subject}")
#     #print(f"From: {email._from}")
#     #print(f"To: {', '.join(email.to)}")
#     #print(f"Received At: {email.created_at}")
#     #print("Body:")
#     print(email.body)
#     print("="*50)  # Separator between emails
from bs4 import BeautifulSoup
import openai

client = openai.OpenAI()
p = """
You are a content editor AI. Your task is to process the text of a newsletter and remove all content related to promotions, advertisements, sponsorships, sales pitches, subscription information, and administrative details (such as bookkeeping, terms, and conditions). Retain only the content that focuses on delivering news, updates, and information relevant to the newsletter’s theme or audience. Ensure the resulting output is coherent and focuses solely on newsworthy content.
"""
from pydantic import BaseModel, Field

class News(BaseModel):
    title: str = Field(description="The title of the news item")
    content: str = Field(description="The content of the section")

class Topic(BaseModel):
    header: str = Field(description="The header of the topic")
    summary: str = Field(description="A brief summary of the topic")
    news: list[News] = Field(description="A list of news items related to the topic")

class Newsletter(BaseModel):
    topics: list[Topic] = Field(description="A list of topics covered in the newsletter")



# Process the retrieved emails with full content
for email in emails[:3]:
    #print(f"Subject: {email.subject}")
    #print(f"From: {email._from}")
    #print(f"To: {', '.join(email.to)}")
    #print(f"Received At: {email.created_at}")
    #print("Body:")
    
    # Use BeautifulSoup to extract the content of the email body, ignoring style and tags
    soup = BeautifulSoup(email.body, 'html.parser')
    email_text = soup.get_text()
    #print(email_text)
    #print("="*50)  # Separator between emails

    repsonse = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[{"role": "system", "content": p}, {"role": "user", "content": email_text}],
        response_format=Newsletter
    )
    if repsonse.choices[0].message.refusal:
        continue
    newsletter = repsonse.choices[0].message.content
    # response = client.chat.completions.create(
    #     model="gpt-4o-mini",
    #     messages=[{"role": "system", "content": p}, {"role": "user", "content": email_text}]
    # )
    # Print the email subject
    print("="*50)
    print(f"Subject: {email.subject}")
    print("-"*50)
    pprint.pprint(newsletter)
    # Print the extracted text from OpenAI
    #print("Extracted Text:")
    #print(response.choices[0].message.content)
    
    # Display in a format that is easy to read
    print("="*50)  # Separator between emails
    #print(response.choices[0].message.content)


client = openai.OpenAI()