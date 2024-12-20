from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import base64
from email.utils import parseaddr
import re

class GmailService:
    def __init__(self, user):
        self.user = user
        self.service = self._create_service()
        
    def _create_service(self):
        """Create Gmail API service"""
        if not self.user.gmail_credentials:
            raise ValueError("Gmail credentials not found")
            
        credentials = Credentials(
            **self.user.gmail_credentials
        )
        return build('gmail', 'v1', credentials=credentials)
    
    def get_newsletters(self):
        """Fetch and identify newsletter emails"""
        results = self.service.users().messages().list(
            userId='me',
            q='category:primary',
            maxResults=100
        ).execute()
        
        messages = results.get('messages', [])
        newsletters = []
        
        for message in messages:
            msg = self.service.users().messages().get(
                userId='me', 
                id=message['id'],
                format='metadata',
                metadataHeaders=['From', 'Subject']
            ).execute()
            
            headers = msg['payload']['headers']
            from_header = next(h for h in headers if h['name'] == 'From')
            subject_header = next(h for h in headers if h['name'] == 'Subject')
            
            sender_email = parseaddr(from_header['value'])[1]
            
            # Basic newsletter detection logic
            if self._is_likely_newsletter(sender_email, subject_header['value']):
                newsletters.append({
                    'id': msg['id'],
                    'sender': from_header['value'],
                    'subject': subject_header['value']
                })
        
        return newsletters
    
    def _is_likely_newsletter(self, sender_email, subject):
        """Determine if an email is likely a newsletter"""
        newsletter_indicators = [
            r'newsletter',
            r'digest',
            r'weekly',
            r'monthly',
            r'update',
            r'roundup'
        ]
        
        # Check sender domain and subject for newsletter indicators
        return any(re.search(pattern, subject.lower()) for pattern in newsletter_indicators) 