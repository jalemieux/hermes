from datetime import datetime, timedelta
import hashlib
import logging
from typing import List
from app.models import AudioFile, Email, News, Newsletter, Source, Summary, Topic, User, db
from app.mailbox_accessor import MailboxAccessor
from bs4 import BeautifulSoup
import openai
from sqlalchemy import select
from pydantic import BaseModel, Field
from config import Config

class NewsletterNameModel(BaseModel):
    newsletter_name: str = Field(description="The inferred name of the newsletter")

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

class PointModel(BaseModel):
    text: str = Field(description="A key point covered in the summary")
    
class SectionModel(BaseModel):
    header: str = Field(description="The header of the section")
    content: str = Field(description="The content of the section")
    
    
synthesis_prompt = """
You are a content editor AI. Your task is to combine the content of a list of newsletters into a comprehensive body of text. Your output must meet the following criteria:
	1.	Structure:
	•	Title: Provide a title that captures the main topic of the summarized content.
	•	Date Range: Specify the date range the summary covers.
	•	Key Points: Create a bullet-point list of the most significant details, ensuring no critical information is lost.
	•	Thematic Subsections: Summarize specific topics under clear headings (e.g., 'AI Developments', 'Hardware and Devices') in paragraph format, covering all relevant aspects of the input text.
	2.	Comprehensiveness:
	•	Capture all the content and details from the input text. If summarization is required, ensure that no essential information is lost.
	•	Highlight any ambiguities or unclear sections from the input, offering possible interpretations or noting them explicitly.
	3.	Clarity and Professionalism:
	•	Maintain a professional tone with clear and organized information.
	•	Summarize concisely yet comprehensively, ensuring completeness.
	4.	Quality Assurance:
	•	After completing the summary, perform a verification step to confirm that all original points have been addressed.
	•	If any information is missing, refine the summary to include it.

Ensure the output remains accurate, coherent, and fully represents the input material. Do not omit any content, do not summarize unless necessary.
"""
class NewsletterModel(BaseModel):
    newsletters : List[str] = Field(description="A list of newsletters")
       

class SummaryModel(BaseModel):
    date_published: str = Field(description="The date the summary was published")
    from_to_date: str = Field(description="The date range the summary covers")
    key_points: list[PointModel] = Field(description="A list of key points covered in the summary")
    title: str = Field(description="The title of the summary")
    sections: list[SectionModel] = Field(description="A list of sections covered in the summary")
    #sources: list[SourceModel] = Field(description="A list of sources used to create the summary")
    #newsletter_names: list[str] = Field(description="A list of newsletter names used to create the summary")

def convert_summary_to_text(summary: SummaryModel) -> str:
    text = f"Summary\n"
    text += f"Date range: {summary.from_to_date}\n\n"
    
    text += "Key Points:\n"
    for point in summary.key_points:
        text += f"  - {point.text}\n"
    text += "\n"
    
    text += "Sections:\n"
    for section in summary.sections:
        text += f"Section: {section.header}\n"
        text += f"{section.content}\n\n"
    
    text += "Sources:\n"
    for source in summary.sources:
        text += f"  - {source.title} ({source.publisher}, {source.date}): {source.url}\n"
    text += "\n"
    
    text += "Newsletters:\n"
    for newsletter_name in summary.newsletter_names:
        text += f"  - {newsletter_name}\n"
    
    return text


class SummaryGenerator:
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=Config.OPENAI_API_KEY)
        self.mailslurp_api_key = Config.MAILSLURP_API_KEY
        
    def _get_date_range(self, user_id):
        # Get the most recent summary for this user
        last_summary = Summary.query.filter_by(user_id=user_id)\
            .order_by(Summary.to_date.desc())\
            .first()
        
        end_date = datetime.now()
        
        if last_summary:
            start_date = last_summary.to_date
        else:
            # If no previous summary, look back 7 days
            start_date = end_date - timedelta(days=7)
            
        return start_date, end_date

    def collect_and_summarize_preprocessed_emails(self, user):
        """
        Collect and summarize preprocessed emails from a given inbox starting from a specified date.
        Uses multiple summarization functions to generate different summaries.
        
        Parameters:
        - user_id: The ID of the user to collect emails from.
        """
    
        # Find all emails for this user that haven't been part of summaries yet
        unsummarized_emails = Email.query.filter_by(user_id=user.id, is_summarized=False).all()
        if len(unsummarized_emails) == 0:
            logging.info(f"No unsummarized emails found for user: {user.email}")
            # return latest summary for user
            latest_summary = Summary.query.filter_by(user_id=user.id).order_by(Summary.date_published.desc()).first()
            if latest_summary and not latest_summary.has_audio:
                return latest_summary
            else:
                logging.info(f"No summaries found for user: {user.email}")
                return None
                    
        logging.info(f"Summarizing {len(unsummarized_emails)} emails")
        summary, sources, newsletter_names = self.summarize_content([email.id for email in unsummarized_emails])
        
        new_summary = Summary(
            user_id=user.id,
            title=f"News Brief - {datetime.now().strftime('%m %d')}",
            from_date=min(email.email_date for email in unsummarized_emails),
            to_date=max(email.email_date for email in unsummarized_emails),
            has_audio=False,
            date_published=datetime.now(),
            status='completed',
            key_points=[{"text": point.text} for point in summary.key_points],
            sections=[{"header": section.header, "content": section.content} for section in summary.sections],
            sources=[{"url": source.url, "date": source.date, "title": source.title, "publisher": source.publisher} for source in sources],
            newsletter_names=list(newsletter_names),
            email_ids=[email.id for email in unsummarized_emails],
        )
        
        # Add the new summary to the database
        db.session.add(new_summary)
        
        # Update the emails to be summarized
        for email in unsummarized_emails:
            email.is_summarized = True
        db.session.commit()
        
        return new_summary

    def collect_and_summarize_emails(self, user_id, start_date):
        """
        Collect and summarize emails from a given inbox starting from a specified date.
        Uses multiple summarization functions to generate different summaries.
        
        Parameters:
        - user_id: The ID of the user to collect emails from.
        - start_date: The start date for fetching emails.
        
        Returns:
        - list[Summary]: List of created summary objects with the generated summary details.
        """
        logging.info(f"Starting to collect and summarize emails for user_id: {user_id} from start_date: {start_date}")
        
        mailbox = MailboxAccessor()
        
        # Calculate days between dates for fetching emails
        days_diff = (datetime.now() - start_date).days
        logging.info(f"Fetching emails from last {days_diff} days")
        mailbox_id = User.query.get(user_id).mailslurp_inbox_id
        emails = mailbox.get_emails_from_last_n_days(mailbox_id, days_diff)
        logging.info(f"Found {len(emails)} emails to process")
        
        if len(emails) == 0:
            return None
        
        # Get all newsletters
        all_newsletters = Newsletter.query.filter_by(user_id=user_id).all()
        newsletter_dict = {newsletter.name: newsletter.is_active for newsletter in all_newsletters}
        logging.info(f"all newsletters: {newsletter_dict}")
        emails_to_process = []
        for email in emails:
            #newsletter_name = self.newsletter_name(all_newsletters, email.sender.email_address, email.subject).newsletter_name
            #print(email)
            newsletter_name = self.newsletter_name(email)
            logging.info(f"identified email as newsletter: {newsletter_name}")
            # Check if the newsletter name is in the list of all newsletters
            if newsletter_name not in newsletter_dict:
                # If not, create a new Newsletter object with is_active set to True
                #print(email.sender)
                new_newsletter = Newsletter(
                    name=newsletter_name,
                    is_active=True,
                    user_id=user_id, 
                    sender=email.sender.email_address,
                    latest_date=datetime.now()
                )
                db.session.add(new_newsletter)
                db.session.commit()
                logging.info(f"Created new active newsletter: {newsletter_name}")
                newsletter_dict[newsletter_name] = True
                emails_to_process.append(email)
            else:
                if not newsletter_dict[newsletter_name]:
                    # If the newsletter is inactive, remove the email from the list
                    logging.info(f"Skipping email from inactive newsletter: {newsletter_name}")
                else:
                    emails_to_process.append(email)
                    logging.info(f"Adding email to process: {email.subject}")
        
        logging.info(f"Filtered emails to {len(emails_to_process)} active newsletter emails")
        if len(emails_to_process) == 0:
            return None
        

        email_ids = self.process_emails(emails_to_process, user_id)
        logging.info(f"Processed content: {email_ids}")
        if len(email_ids) == 0:
            return None
        
        # List of summarization functions to use
        summarization_functions = [
            ('summarize_content', self.summarize_content),
        ]
        
        summaries = []
        for func_name, summarize_func in summarization_functions:
            logging.info(f"Generating summary using {func_name}")
            summary, sources, newsletter_names = summarize_func(email_ids)
            logging.info(f"Generated summary using {func_name}")
            
            new_summary = Summary(
                user_id=user_id,
                title=f"Recap - {datetime.now().strftime('%Y-%m-%d')}",
                from_date=start_date,
                to_date=datetime.now(),
                has_audio=False,
                date_published=datetime.now(),
                status='completed',
                key_points=[{"text": point.text} for point in summary.key_points],
                sections=[{"header": section.header, "content": section.content} for section in summary.sections],
                sources=[{"url": source.url, "date": source.date, "title": source.title, "publisher": source.publisher} for source in sources],
                newsletter_names=list(newsletter_names),
                email_ids=email_ids,
            )
            
            # Add the new summary to the database
            db.session.add(new_summary)
            db.session.commit()
            logging.info(f"Successfully created summary for user_id: {user_id} using {func_name}")
            
            summaries.append(new_summary)
        
        if not summaries:
            raise Exception("Failed to generate any summaries")
        
        return summaries

    def process_inbox_emails(self, user_id, start_date=None):
        """
        Process emails from a user's inbox to extract and summarize newsletter content.
        
        Parameters:
        - user_id: The ID of the user whose inbox emails are being processed.
        - start_date: The start date for fetching emails (optional).
        
        Raises:
        - ValueError: If the user is not found or has no mailbox configured.
        
        Logs:
        - Information about the processing steps and any errors encountered.
        """
        logging.info(f"Starting to process inbox emails for user_id: {user_id}")
        
        mailbox = MailboxAccessor()
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)
        
        # Get user's inbox ID
        user = User.query.get(user_id)
        if not user or not user.mailslurp_inbox_id:
            logging.error(f"User not found or has no mailbox configured. User ID: {user_id}")
            raise ValueError("User not found or has no mailbox configured")
        
        inbox_id = user.mailslurp_inbox_id
        logging.info(f"Processing emails from inbox: {inbox_id}")
        
        # Calculate days between dates for fetching emails
        days_diff = (datetime.now() - start_date).days + 1
        logging.info(f"Fetching emails from last {days_diff} days")
        
        emails = mailbox.get_emails_from_last_n_days(inbox_id, days_diff)
        logging.info(f"Found {len(emails)} emails to process")

        system_prompt = """
        You are a content editor AI. Your task is to process the text of a newsletter and remove all content related to 
        promotions, advertisements, sponsorships, sales pitches, subscription information, and administrative details. 
        Retain only the content that focuses on delivering news, updates, and information relevant to the newsletter's 
        theme or audience. Ensure the resulting output is coherent and focuses solely on newsworthy content.
        """
        

        for email in emails:
            email_subject = hashlib.sha256(email.subject.encode('utf-8')).hexdigest()
            email_from = hashlib.sha224(email._from.encode('utf-8')).hexdigest()
            email_date = str(int(email.created_at.timestamp()))
            unique_identifier = f"{email_subject}_{email_from}_{email_date}"
            
            logging.debug(f"Processing email - Subject: {email.subject}, From: {email._from}")
            
            email_record = Email.query.filter_by(unique_identifier=unique_identifier).first()
            if not email_record:
                logging.info(f"Processing new email: {email.subject}")
                soup = BeautifulSoup(email.body, 'html.parser')
                email_text = soup.get_text()
                logging.debug("Successfully extracted text from email HTML")

                # LLM based name inferrence: 
                #newsletter_name = self.newsletter_name(email).newsletter_name
                newsletter_name = email.sender.name
                logging.info(f"Newsletter name: {email.sender}")
                # Check if this newsletter name already exists for this user
                existing_excluded_newsletter = Newsletter.query.filter_by(
                    user_id=user_id,
                    name=newsletter_name, 
                    is_active=False
                ).first()
                
                # known newsletter the user doesn't want to see in newsfeed.
                if existing_excluded_newsletter:
                    logging.debug(f"Newsletter {email_model.name} already exists, skipping...")
                    # Create email record with unique identifier only
                    email_record = Email(
                        user_id=user_id,
                        unique_identifier=unique_identifier,
                        name=email_model.name,
                        email_date=email.created_at, 
                        is_excluded=True
                    )
                    db.session.add(email_record)
                    db.session.commit()
                    db.session.refresh(email_record)
                    continue

                logging.debug(f"Created email record with unique identifier: {unique_identifier}")
                logging.debug("Sending to OpenAI for processing...")
                response = self.openai_client.beta.chat.completions.parse(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": email_text}
                    ],
                    response_format=EmailModel
                )
                

                email_model = response.choices[0].message.parsed
                email_model.name = newsletter_name

                logging.debug(f"Successfully parsed newsletter: {email_model.name}")
                
                # Store the email in the database
                email_record = Email(
                    user_id=user_id,
                    unique_identifier=unique_identifier,
                    name=email_model.name,
                    email_date=email.created_at
                )
                db.session.add(email_record)
                
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
                db.session.refresh(email_record)
                logging.info(f"Successfully saved email record with ID: {email_record.id}")

                # Process newsletter record
                newsletter = Newsletter.query.filter_by(name=email_model.name).first()
                if not newsletter:
                    logging.info(f"Creating new newsletter record: {email_model.name}")
                    newsletter = Newsletter(
                        user_id=user_id,
                        sender=email._from,
                        name=email_model.name, 
                        is_active=True,
                        latest_date=email.created_at
                    )
                    db.session.add(newsletter)
                else:
                    logging.debug(f"Updating existing newsletter: {email_model.name}")
                    newsletter.latest_date = email.created_at
                
                db.session.commit()
            else:
                logging.debug(f"Skipping already processed email: {email.subject}")

        logging.info("Completed processing inbox emails")
        return True



    def fetch_emails(self, inbox_id, start_date, end_date):
        mailbox = MailboxAccessor()
        
        # Calculate days between dates for fetching emails
        days_diff = (end_date - start_date).days + 1
        emails = mailbox.get_emails_from_last_n_days(inbox_id, days_diff)
        return emails



    

    def process_emails(self, emails, user_id):
        """
        Processes a list of emails to extract and store relevant content in the database.

        This function takes a list of email objects and a user ID, processes each email to remove 
        non-newsworthy content, and stores the processed content in the database. It ensures that 
        each email is uniquely identified and only processes emails that have not been previously 
        stored.

        Parameters:
        - emails (list): A list of email objects to be processed.
        - user_id (int): The ID of the user to whom the emails belong.

        Returns:
        - list: A list of IDs of the processed emails stored in the database.
        """
        system_prompt = """
        You are a content editor AI. Your task is to process the text of a newsletter and remove all content related to 
        promotions, advertisements, sponsorships, sales pitches, subscription information, and administrative details. 
        Retain only the content that focuses on delivering news, updates, and information relevant to the newsletter's 
        theme or audience. Ensure the resulting output is coherent and focuses solely on newsworthy content.
        """

        email_ids = []
        for email in emails:
            email_subject = hashlib.sha256(email.subject.encode('utf-8')).hexdigest()
            email_from = hashlib.sha256(email._from.encode('utf-8')).hexdigest()
            email_sender = email._from
            email_date = str(int(email.created_at.timestamp()))
            unique_identifier = f"{email_subject}_{email_from}_{email_date}"
            email_record = Email.query.filter_by(unique_identifier=unique_identifier).first()
            
            # If email doesn't already exist in the database, process it
            if not email_record:
                logging.debug(f"new email: {email.subject}")
                # Extract text content from HTML
                soup = BeautifulSoup(email.body, 'html.parser')
                email_text = soup.get_text()
                logging.debug("extracted text")
                response = self.openai_client.beta.chat.completions.parse(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": email_text}
                    ],
                    response_format=EmailModel
                )
                
                email_model = response.choices[0].message.parsed
                logging.debug("parsed newsletter")
                
                # Store the email in the database
                email_record = Email(
                    user_id=user_id,
                    unique_identifier=unique_identifier,
                    name=email_model.name,
                    email_date=email.created_at
                )
                db.session.add(email_record)
                for topic in email_model.topics:
                    topic_record = Topic(
                        email=email_record,
                        header=topic.header,
                        summary=topic.summary
                    )
                    db.session.add(topic_record)
                    for news in topic.news:
                        news_record = News(
                            topic=topic_record,
                            title=news.title,
                            content=news.content,
                        )
                        db.session.add(news_record)
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
                db.session.refresh(email_record)
                id = email_record.id
                logging.debug(f"saved email")
            else:
                id = email_record.id
                logging.debug(f"existing email: {email.subject}")
            email_ids.append(id)
        return email_ids
    
    def summarize_content(self, email_ids) -> tuple[SummaryModel, list[SourceModel], list[str]]:

        # get all the source content   
        content = []
        sources = {}
        newsletter_names = set()
        emails = Email.query.filter(Email.id.in_(email_ids)).all()
        for email in emails:
            logging.info(f"email: {email.name}")
            content.append(f"newsletter: {email.name}\n{email.to_newsletter()}")
            newsletter_names.add(email.name)
            for source in email.sources:
                if source.url not in sources:
                    sources[source.url] = source

        parsed = self.openai_client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": synthesis_prompt},
                {"role": "user", "content": str(content)}
            ],
            response_format=SummaryModel
        )
        logging.info(f"parsed summary")
        summary = parsed.choices[0].message.parsed
        sources = list(sources.values())
        return summary, sources, newsletter_names
    
    
    def synthesis(self, email_ids) -> tuple[SummaryModel, list[SourceModel], list[str]]:

        # get all the source content   
        content = []
        sources = {}
        newsletter_names = set()
        emails = Email.query.filter(Email.id.in_(email_ids)).all()
        for email in emails:
            logging.info(f"email: {email.name}")
            content.append(email.to_newsletter())
            newsletter_names.add(email.name)
            for source in email.sources:
                if source.url not in sources:
                    sources[source.url] = source

        parsed = self.openai_client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": synthesis_prompt},
                {"role": "user", "content": str(content)}
            ],
            response_format=SummaryModel
        )
        logging.info(f"parsed summary")
        summary = parsed.choices[0].message.parsed
        sources = list(sources.values())
        return summary, sources, newsletter_names
    

    
    def generate_summary(self, user_id, new_summary, start_date = None, end_date = None) -> Summary:
        """
        Generates a summary for a given user within a specified date range.
        
        This function fetches emails, processes them, synthesizes a summary, and updates the summary record.
        
        Parameters:
        - user_id: The ID of the user for whom the summary is being generated.
        - new_summary: The Summary object to be updated with the generated summary details.
        - start_date: The start date for fetching emails (optional).
        - end_date: The end date for fetching emails (optional).
        
        Returns:
        - Summary: The updated Summary object with the generated summary details.
        """
        user = User.query.get(user_id)
        inbox_id = user.mailslurp_inbox_id

        if start_date is None or end_date is None:
            start_date, end_date = self._get_date_range(user_id)
        logging.info(f"start_date: {start_date}, end_date: {end_date}")

        emails = self.fetch_emails(inbox_id, start_date, end_date)
        logging.info(f"Fetched {len(emails)} emails")
        if len(emails) == 0:
            logging.info(f"No emails found")
            raise Exception("No emails found")
        
        email_ids = self.process_emails(emails, user_id)
        logging.info(f"Processed content: {email_ids}")
        
        summary, sources, newsletter_names = self.synthesis(email_ids)
        logging.info(f"Synthesized summary")
        
        new_summary.title = "Summary of your newsletters"
        new_summary.from_to_date = f"{start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}"
        new_summary.from_date = start_date
        new_summary.to_date = end_date
        new_summary.has_audio = False
        new_summary.date_published = datetime.now()
        new_summary.status = 'completed'
        new_summary.key_points = [{"text": point.text} for point in summary.key_points]
        new_summary.sections = [{"header": section.header, "content": section.content} for section in summary.sections]
        new_summary.sources = [{"url": source.url, "date": source.date, "title": source.title, "publisher": source.publisher} for source in sources]
        new_summary.newsletter_names = list(newsletter_names)   
        new_summary.email_ids = email_ids
        # Add the new summary to the database
        return new_summary
    
 
        

    def identify_newsletters(self, inbox_id):
        """Identify unique newsletters by analyzing email subjects from the last 24 hours"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=1)
        
        # Fetch emails for the last 24 hours
        emails = self.fetch_emails(inbox_id, start_date, end_date)
        
        # Get all newsletters
        all_newsletters = Newsletter.query.all()
        newsletter_dict = {newsletter.name: newsletter.is_active for newsletter in all_newsletters}
        logging.info(f"all newsletters: {newsletter_dict}")
        emails_to_process = []
        for email in emails:
            newsletter_name = self.newsletter_name(email)
            logging.info(f"identified email as newsletter: {newsletter_name}")
            # Check if the newsletter name is in the list of all newsletters
            if newsletter_name not in newsletter_dict:
                # If not, create a new Newsletter object with is_active set to True
                new_newsletter = Newsletter(
                    name=newsletter_name,
                    is_active=True,
                    user_id=email.user_id, 
                    sender=email.sender.email_address,
                    latest_date=datetime.now()
                )
                db.session.add(new_newsletter)
                db.session.commit()
                logging.info(f"Created new active newsletter: {newsletter_name}")
                newsletter_dict[newsletter_name] = True
                emails_to_process.append(email)
            else:
                if not newsletter_dict[newsletter_name]:
                    # If the newsletter is inactive, remove the email from the list
                    logging.info(f"Skipping email from inactive newsletter: {newsletter_name}")
                else:
                    emails_to_process.append(email)
                    logging.info(f"Adding email to process: {email.subject}")
        
        logging.info(f"Filtered emails to {len(emails_to_process)} active newsletter emails")
        return emails_to_process

    

    def convert_to_audio_format(self, email_text: str) -> str:
        """Convert email content to a more audio-friendly format using OpenAI."""
        system_prompt = """
        You are an AI assistant that converts newsletter content into a natural, 
        conversational format suitable for text-to-speech. Your task is to:
        1. Maintain the key information and structure
        2. Make the text flow naturally when read aloud
        3. Convert any visual elements (bullets, formatting) into spoken transitions
        4. Add appropriate pauses and transitions between sections
        5. Do not add any additional text or commentary
        6. Do not sound overly enthusiast and don't use workds like 'exciting' or 'amazing'
        """
        
        response = self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": email_text}
            ]
        )
        
        return response.choices[0].message.content

    def newsletter_name(self, email) -> str:
        return self.newsletter_sender(f"{str(email.sender)} {str(email.subject)} {str(email.text_excerpt)} {str(email.recipients)}")


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
    
    def inferred_newsletter_name(self, newsletters, email_sender, email_subject):
        prompt = f"""
        Your task is to infer the newsletter name given an email. 
        You will be given a list of known newsletters to help you match the email to an existing newsletter.
        You will be given the email subject and sender. 
        If you can't match to an existing newsletter name, return a new name you infer from the email.
         
         Newsletters names: {", ".join([newsletter.name for newsletter in newsletters])}
        """
        parsed = self.openai_client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f'email subject: {email_subject}, email sender: {email_sender}'}
            ],
            response_format=NewsletterNameModel
        )
        return parsed.choices[0].message.parsed
    

    

def test_fetch_emails(summary_generator):
    user_id = 1
    user = User.query.get(user_id)
    inbox_id = user.mailslurp_inbox_id
    start_date, end_date = summary_generator._get_date_range(user_id)
    print(f"start_date: {start_date}, end_date: {end_date}")
    emails = summary_generator.fetch_emails(inbox_id, start_date, end_date)
    print(f"Fetched {len(emails)} emails")
    return emails
    
def test_process_emails(summary_generator):
    emails = test_fetch_emails(summary_generator)
    
    email_ids = summary_generator.process_emails(emails[:1], 1)
    print(f"Processed content: {email_ids}")
    return email_ids

def test_synthesize_newsletter(summary_generator):
    email_ids = test_process_emails(summary_generator)
    summary = summary_generator.synthesis(email_ids)
    print(convert_summary_to_text(summary))
    
