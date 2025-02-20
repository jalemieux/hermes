
from app.models import User
from app.summary_generator import SummaryGenerator
from datetime import datetime, timedelta
import hashlib
import logging
import os
import threading
from typing import List
from app.models import AudioFile, Email, News, Newsletter, Source, Summary, Topic, User, db
from app.mailbox_accessor import MailboxAccessor
from bs4 import BeautifulSoup
import openai
from pydantic import BaseModel, Field

from config import Config

# Configure logging to include process id and thread id
logging.basicConfig(format='%(asctime)s - %(process)d - %(thread)d - %(levelname)s - %(message)s', level=logging.INFO)

class EmailSenderModel(BaseModel):
    sender: str = Field(description="The inferred sender of the email")

class NewsModel(BaseModel):
    title: str = Field(description="The title of the news item")
    content: str = Field(description="The content of the section")

class TopicModel(BaseModel):
    header: str = Field(description="The header of the topic")
    summary: str = Field(description="A brief summary of the topic")
    news: list[NewsModel] = Field(description="A list of news items related to the topic")

class SourceModel(BaseModel):
    url: str = Field(description="The url of the source")
    date: str = Field(description="The date of the source")
    title: str = Field(description="The title of the source")
    publisher: str = Field(description="The publisher of the source")


class EmailModel(BaseModel):
    topics: list[TopicModel] = Field(description="A list of topics covered in the newsletter")
    sources: list[SourceModel] = Field(description="A list of sources used to create the newsletter")
    name: str = Field(description="The inferred name of the newsletter")

def convert_newsletter_to_text(newsletter: EmailModel) -> str:
    text = f"Newsletter: {newsletter.name}\n\n"
    
    for topic in newsletter.topics:
        text += f"Topic: {topic.header}\n"
        text += f"Summary: {topic.summary}\n"
        for news in topic.news:
            text += f"  - {news.title}: {news.content}\n"
        text += "\n"
    
    text += "Sources:\n"
    for source in newsletter.sources:
        text += f"  - {source.title} ({source.publisher}, {source.date}): {source.url}\n"
    
    return text

class EmailProcessor:
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=Config.OPENAI_API_KEY)
        self.mailbox = MailboxAccessor()
    def parse_email(self, email_text):
        system_prompt = """
        You are a content editor AI. Your task is to process the text of a newsletter and remove all content related to 
        promotions, advertisements, sponsorships, sales pitches, subscription information, and administrative details. 
        Retain only the content that focuses on delivering news, updates, and information relevant to the newsletter's 
        theme or audience. Ensure the resulting output is coherent and focuses solely on newsworthy content.
        """ 
        response = self.openai_client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": email_text}
            ],
            response_format=EmailModel
        )

        email_model = response.choices[0].message.parsed
        email_model.name = email_model.name.strip()
        for topic in email_model.topics:
            topic.header = topic.header.strip()
            topic.summary = topic.summary.strip()
            for news in topic.news:
                news.title = news.title.strip()
                news.content = news.content.strip()
        for source in email_model.sources:
            source.url = source.url.strip()
            source.title = source.title.strip()
            source.publisher = source.publisher.strip()
        return email_model
    

      
    
    def newsletter_sender(self, email_raw) -> str:
        prompt = f"""
        Your task is to find the original sender of a newsletter. You will be given the raw content of an email that may have been forwarded, you will need to identify the original sender.
        Here's an example of a forwarded email, where the original sender is `TLDR AI <dan@tldrnewsletter.com>`:
            ```
            'sender': {{'email_address': 'jalemieux@gmail.com',
            'name': 'Jac Lemieux',
            'raw_value': 'Jac Lemieux <jalemieux@gmail.com>'}},
             'subject': "Fwd: Hugging Face's Open-R1 💻, OpenAI's Model for Government Use "
                            '🏛️, DeepSeek: All About Apps Now 📱',
            'team_access': True,
            'text_excerpt': '---------- Forwarded message ---------\r\n'
                            'From: TLDR AI <dan@tldrnewsletter.com>\r\n'
                            'Date: Wed, Jan 29, 2',
            ```
        
        """
        parsed = self.openai_client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f'email: {email_raw}'}
            ],
            response_format=EmailSenderModel
        )
        return parsed.choices[0].message.parsed.sender
    
    def process_user_emails(self, user_id, days_back : int = 1):
        """
        
        Process user emails from the last specified number of days.

        This function retrieves emails from the user's inbox, processes each email to extract relevant content, 
        and stores the processed email in the database. 

        Args:
            user_id (int): The ID of the user whose emails are to be processed.
            days_back (int, optional): The number of days back to retrieve emails from. Defaults to 1.

        Returns:
            bool: True if the processing is completed successfully.
        
        Raises:
            ValueError: If the user is not found or has no mailbox configured.
        
        """
        # Get user's inbox ID
        user = User.query.get(user_id)
        logging.info(f"Processing user {user.email}")
        if not user or not user.mailslurp_inbox_id:
            logging.error(f"User not found or has no mailbox configured. User ID: {user_id}")
            raise ValueError("User not found or has no mailbox configured")
                
        inbox_id = user.mailslurp_inbox_id
        logging.info(f"Processing emails from inbox: {inbox_id}")
        
    
        emails = self.mailbox.get_emails_from_last_n_days(inbox_id, days_back)
        logging.info(f"Found {len(emails)} emails to process")
        
        #users_newsletter = Newsletter.query.filter_by(user_id=user_id).all()
        #users_newsletter_dict = {newsletter.name: newsletter.is_active for newsletter in users_newsletter}

        for email in emails:
            email_subject = hashlib.sha256(email.subject.encode('utf-8')).hexdigest()
            email_from = hashlib.sha224(email._from.encode('utf-8')).hexdigest()
            email_date = str(int(email.created_at.timestamp()))
            unique_identifier = f"{email_subject}_{email_from}_{email_date}"
            
            logging.debug(f"Processing email - Subject: {email.subject}, From: {email._from}")
            
            email_record = Email.query.filter_by(unique_identifier=unique_identifier, user_id=user_id).first()
            if email_record:
                logging.info(f"Skipping already processed email: {email.subject}")
                continue
            
            logging.info(f"Processing new email: {email.subject}")
            soup = BeautifulSoup(email.body, 'html.parser')
            email_text = soup.get_text(strip=True)
            logging.debug("Successfully extracted text from email HTML")

            # find the email newsletter name
            newsletter_sender = self.newsletter_sender(f"{str(email.sender)} {str(email.subject)} {str(email.text_excerpt)} {str(email.recipients)}")

            logging.info(f"Newsletter name: {newsletter_sender}")
            #newsletter_should_be_processed = users_newsletter_dict[newsletter_sender]
 
            email_model = self.parse_email(email_text)
            email_extracted_content = convert_newsletter_to_text(email_model)
            

            # Store the email in the database
            email_record = Email(
                user_id=user_id,
                unique_identifier=unique_identifier,
                sender=newsletter_sender,
                email_date=email.created_at,
                text_content=email_text,
                cleaned_content=email_extracted_content,
                name=email_model.name
            )
            db.session.add(email_record)
            db.session.commit()
            db.session.refresh(email_record)
            
            # Add topics
            for topic in email_model.topics:
                topic_record = Topic(
                    email=email_record,
                    header=topic.header,
                    summary=topic.summary
                )
                db.session.add(topic_record)
                
                # Add news items
                for news in topic.news:
                    news_record = News(
                        topic=topic_record,
                        title=news.title,
                        content=news.content,
                    )
                    db.session.add(news_record)
            
            # Add sources
            for source in email_model.sources:
                source_record = Source(
                    email=email_record,
                    url=source.url,
                    date=source.date,
                    title=source.title,
                    publisher=source.publisher
                )
                db.session.add(source_record)
            
            db.session.commit()
            logging.info(f"Successfully saved email record with ID: {email_record.id}")

        logging.info("Completed processing inbox emails")
        return True
     
