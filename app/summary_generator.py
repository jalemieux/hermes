from datetime import datetime, timedelta
import hashlib
import logging
from app.models import Email, Summary, User, db
from app.mailbox_accessor import MailboxAccessor
from bs4 import BeautifulSoup
import openai
from pydantic import BaseModel, Field
from config import Config

class News(BaseModel):
    title: str = Field(description="The title of the news item")
    content: str = Field(description="The content of the section")

class Topic(BaseModel):
    header: str = Field(description="The header of the topic")
    summary: str = Field(description="A brief summary of the topic")
    news: list[News] = Field(description="A list of news items related to the topic")

class Newsletter(BaseModel):
    topics: list[Topic] = Field(description="A list of topics covered in the newsletter")

class Point(BaseModel):
    text: str = Field(description="A key point covered in the summary")
    
class Section(BaseModel):
    header: str = Field(description="The header of the section")
    content: str = Field(description="The content of the section")
    
class Source(BaseModel):
    url: str = Field(description="The url of the source")
    date: str = Field(description="The date of the source")
    title: str = Field(description="The title of the source")
    publisher: str = Field(description="The publisher of the source")
    
class SummaryModel(BaseModel):
    date_published: str = Field(description="The date the summary was published")
    from_to_date: str = Field(description="The date range the summary covers")
    key_points: list[Point] = Field(description="A list of key points covered in the summary")
    sections: list[Section] = Field(description="A list of sections covered in the summary")
    sources: list[Source] = Field(description="A list of sources used to create the summary")

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

    def _process_email_content(self, email_text) -> Newsletter:
        system_prompt = """
        You are a content editor AI. Your task is to process the text of a newsletter and remove all content related to 
        promotions, advertisements, sponsorships, sales pitches, subscription information, and administrative details. 
        Retain only the content that focuses on delivering news, updates, and information relevant to the newsletter's 
        theme or audience. Ensure the resulting output is coherent and focuses solely on newsworthy content.
        """
        
        try:
            response = self.openai_client.beta.chat.completions.parse(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": email_text}
                ],
                response_format=Newsletter
            )
            return response.choices[0].message.parsed
        except Exception as e:
            print(f"Error processing email content: {e}")
            return None

    def fetch_and_process_emails(self, user_id, inbox_id, start_date, end_date):
        logging.debug(f"Fetching emails for user {user_id} with inbox {inbox_id} from {start_date} to {end_date}")
        # Initialize MailboxAccessor
        mailbox = MailboxAccessor(self.mailslurp_api_key, inbox_id)
        
        # Calculate days between dates for fetching emails
        days_diff = (end_date - start_date).days + 1
        emails = mailbox.get_emails_from_last_n_days(days_diff)
        logging.debug(f"Fetched {len(emails)} emails for days {days_diff}")
        email_ids = []
        for email in emails:
            email_subject = hashlib.sha256(email.subject.encode('utf-8')).hexdigest()
            email_from = hashlib.sha256(email._from.encode('utf-8')).hexdigest()
            email_date = str(int(email.created_at.timestamp()))
            unique_identifier = f"{email_subject}_{email_from}_{email_date}"
            email_record = Email.query.filter_by(unique_identifier=unique_identifier).first()
            # If email doesn't already exist in the database, process it
            if not email_record:
                # Extract text content from HTML
                soup = BeautifulSoup(email.body, 'html.parser')
                email_text = soup.get_text()
                
                # Process content using OpenAI
                processed = self._process_email_content(email_text)
                
                # Create a unique identifier based on the email subject, the from and the date
                
                
                # Store the email in the database
                email_record = Email(
                    user_id=user_id,
                    unique_identifier=unique_identifier,
                    email_text=email_text, 
                    email_date=email.created_at
                )
                db.session.add(email_record)
                db.session.commit()
                db.session.refresh(email_record)
                id = email_record.id
            else:
                id = email_record.id
            
            email_ids.append(id)
        return email_ids
    
    def synthesized_summary(self, emails):
        prompt = """
        You are a content editor AI. Your task is to synthesize a summary from a list of texts.
         Generate a concise summary from the provided collection of text. Structure the summary as follows:
	1.	A title that captures the main topic of the summarized content.
	2.	A date range the summary covers.
	3.	A ‘Key Points’ section with bullet points highlighting the most significant details.
	4.	Thematic subsections (e.g., ‘AI Developments’, ‘Hardware and Devices’) summarizing specific topics in a paragraph format.
	5.	A ‘Sources’ section listing the source titles, publication names, and publication dates, with an optional call-to-action like ‘Read original.’

Ensure the tone is professional, the information is clear and well-organized, and the summary is concise yet comprehensive.
        """

        parsed = self.openai_client.beta.chat.completions.parse(
            model="gpt-4",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": "\n\n".join(emails)}
            ],
            response_format=SummaryModel
        )
        return parsed.choices[0].message.parsed
    
    def create_summary(self, user_id):
        start_date, end_date = self._get_date_range(user_id)
        # load user and inbox id
        user = User.query.get(user_id)
        inbox_id = user.inbox_id
        email_ids = self.fetch_and_process_emails(user_id, inbox_id, start_date, end_date)
        # load all emails
        emails = Email.query.filter(Email.id.in_(email_ids)).all()
        summary = self.synthesized_summary(emails)
        return summary
        # # Create final summary
        # if processed_content:
        #     summary = Summary(
        #         user_id=user_id,
        #         content=str(processed_content),  # Store processed content
        #         title=f"News Summary {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
        #         from_date=start_date,
        #         to_date=end_date
        #     )
            
        #     db.session.add(summary)
        #     db.session.commit()
            
        #     return summary
        
        # return None



if __name__ == "__main__":
    summary_generator = SummaryGenerator()
    start_date, end_date = summary_generator._get_date_range(1)
    print(start_date, end_date)
    #summary = summary_generator.create_summary(1)
    #print(summary)