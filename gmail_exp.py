import os.path
import base64
import logging
from typing import List, Dict, Optional, Union
from email import message_from_bytes
from email.message import Message
from datetime import datetime, timedelta
from collections import Counter
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import email.utils
import pytz

class GmailService:
    """A service class for interacting with Gmail API with email analysis capabilities."""
    
    DEFAULT_SCOPES = [
        'https://www.googleapis.com/auth/gmail.readonly',
       # 'https://www.googleapis.com/auth/gmail.modify'
    ]
    
    def __init__(
        self,
        credentials_path: str = 'credentials.json',
        token_path: str = 'token.json',
        scopes: Optional[List[str]] = None,
        log_level: int = logging.DEBUG
    ):
        """Initialize the Gmail service."""
        # Previous initialization code remains the same
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.scopes = scopes or self.DEFAULT_SCOPES
        
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self.logger.addHandler(handler)
        
        self.service = self.authenticate_gmail()

    def authenticate_gmail(self):
        """Authenticate and create the Gmail API service."""
        # Previous authentication code remains the same
        try:
            if not os.path.exists(self.credentials_path):
                raise FileNotFoundError(
                    f"Credentials file not found at {self.credentials_path}"
                )
            
            creds = None
            if os.path.exists(self.token_path):
                creds = Credentials.from_authorized_user_file(self.token_path, self.scopes)
            
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path, self.scopes
                    )
                    creds = flow.run_local_server(port=0)
                
                with open(self.token_path, 'w') as token:
                    token.write(creds.to_json())
            
            return build('gmail', 'v1', credentials=creds)
            
        except Exception as error:
            self.logger.error(f"Authentication failed: {error}")
            raise

    def get_recent_email_titles(
        self,
        days: int = 7,
        max_results: int = 500,
        include_spam_trash: bool = False
    ) -> List[Dict]:
        """
        Retrieve email titles from the last specified number of days.
        
        Args:
            days: Number of days to look back
            max_results: Maximum number of emails to analyze
            include_spam_trash: Whether to include spam/trash emails
            
        Returns:
            List of dictionaries containing email metadata
        """
        try:
            # Calculate the date range
            end_date = datetime.now(pytz.UTC)
            start_date = end_date - timedelta(days=days)
            
            # Construct the Gmail query
            query = f'after:{start_date.strftime("%Y/%m/%d")} before:{end_date.strftime("%Y/%m/%d")}'
            
            # Get messages matching the date range
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results,
                includeSpamTrash=include_spam_trash
            ).execute()
            
            messages = results.get('messages', [])
            self.logger.info(f"Found {len(messages)} messages in the last {days} days")
            
            # Get message details
            email_data = []
            for msg in messages:
                message_data = self.get_message_metadata(msg['id'])
                if message_data:
                    email_data.append(message_data)
            
            return email_data
            
        except HttpError as error:
            self.logger.error(f"Error retrieving recent messages: {error}")
            return []

    def get_message_metadata(self, msg_id: str) -> Optional[Dict]:
        """
        Retrieve only the metadata of a message (more efficient than full message).
        
        Args:
            msg_id: The ID of the message
            
        Returns:
            Dictionary containing message metadata
        """
        try:
            msg = self.service.users().messages().get(
                userId='me',
                id=msg_id,
                format='metadata',
                metadataHeaders=['Subject', 'From', 'Date']
            ).execute()
            
            headers = msg.get('payload', {}).get('headers', [])
            
            # Extract headers into a dictionary
            header_dict = {
                header['name'].lower(): header['value']
                for header in headers
            }
            
            return {
                'id': msg_id,
                'thread_id': msg.get('threadId'),
                'subject': header_dict.get('subject', 'No Subject'),
                'from': header_dict.get('from', 'Unknown'),
                'date': header_dict.get('date'),
                'timestamp': email.utils.parsedate_to_datetime(
                    header_dict.get('date')
                ) if header_dict.get('date') else None
            }
            
        except HttpError as error:
            self.logger.error(f"Error retrieving message metadata {msg_id}: {error}")
            return None

    def analyze_email_titles(
        self,
        days: int = 7,
        max_results: int = 500,
        min_occurrences: int = 2
    ) -> Dict:
        """
        Analyze email titles to find common patterns and frequent senders.
        
        Args:
            days: Number of days to analyze
            max_results: Maximum number of emails to analyze
            min_occurrences: Minimum occurrences to include in trends
            
        Returns:
            Dictionary containing analysis results
        """
        emails = self.get_recent_email_titles(days, max_results)
        
        # Extract titles and senders
        titles = [email['subject'] for email in emails if email.get('subject')]
        senders = [email['from'] for email in emails if email.get('from')]
        
        # Count occurrences
        title_counter = Counter(titles)
        sender_counter = Counter(senders)
        
        # Filter for minimum occurrences
        common_titles = {
            title: count
            for title, count in title_counter.most_common()
            if count >= min_occurrences
        }
        
        common_senders = {
            sender: count
            for sender, count in sender_counter.most_common(10)
        }
        
        return {
            'total_emails': len(emails),
            'common_titles': common_titles,
            'top_senders': common_senders,
            'time_period': f'Last {days} days',
            'analysis_date': datetime.now().isoformat()
        }

# Usage script
def main():
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    try:
        # Initialize the Gmail service
        gmail_service = GmailService()
        
        # Analyze emails from the last week
        analysis = gmail_service.analyze_email_titles(
            days=7,
            max_results=500,
            min_occurrences=2
        )
        
        # Print the results
        print("\nEmail Analysis Results")
        print("=====================")
        print(f"Time Period: {analysis['time_period']}")
        print(f"Total Emails Analyzed: {analysis['total_emails']}")
        
        print("\nMost Common Email Titles:")
        for title, count in analysis['common_titles'].items():
            print(f"- {title} ({count} occurrences)")
        
        print("\nTop Senders:")
        for sender, count in analysis['top_senders'].items():
            print(f"- {sender} ({count} emails)")

    except Exception as error:
        logger.error(f"An error occurred: {error}")
        raise

if __name__ == "__main__":
    main()