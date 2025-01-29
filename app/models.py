# app/models.py
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime, timedelta
import secrets

from config import Config

db = SQLAlchemy(engine_options={'pool_pre_ping': True})

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.Text)
    digest_frequency = db.Column(db.String(20), default='daily')
    
    # Add Google OAuth fields
    google_token = db.Column(db.Text)
    google_refresh_token = db.Column(db.Text)
    google_token_expiry = db.Column(db.DateTime)
    
    # Add MailSlurp fields
    mailslurp_email_address = db.Column(db.String(120))
    mailslurp_inbox_id = db.Column(db.String(120))
    
    # Add relationship to summaries
    #summaries = db.relationship('Summary', backref='user', lazy=True)

    email_forwarding_enabled = db.Column(db.Boolean, default=False)
    # SQL equivalent:
    # ALTER TABLE user ADD COLUMN email_forwarding_enabled BOOLEAN DEFAULT FALSE;

    # Add fields for password reset
    reset_token = db.Column(db.String(100), unique=True)
    reset_token_expiry = db.Column(db.DateTime)

    gmail_credentials = db.Column(db.JSON)
    selected_newsletters = db.Column(db.JSON)  # Store selected newsletter configurations
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_reset_token(self):
        """Generate a password reset token that expires in 1 hour"""
        self.reset_token = secrets.token_urlsafe(32)
        self.reset_token_expiry = datetime.now() + timedelta(hours=1)
        db.session.commit()
        return self.reset_token

    def verify_reset_token(self, token):
        """Verify if the reset token is valid and not expired"""
        if (self.reset_token != token or 
            not self.reset_token_expiry or 
            datetime.now() > self.reset_token_expiry):
            return False
        return True

    def clear_reset_token(self):
        """Clear the reset token after it's been used"""
        self.reset_token = None
        self.reset_token_expiry = None
        db.session.commit()

    def update_gmail_credentials(self, credentials):
        """Update Gmail credentials"""
        self.gmail_credentials = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        db.session.commit()

class Summary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    content = db.Column(db.Text)
    status = db.Column(db.String(100), default='pending')
    title = db.Column(db.String(200))
    has_audio = db.Column(db.Boolean, default=False)
    from_date = db.Column(db.DateTime, nullable=False)
    to_date = db.Column(db.DateTime, nullable=False)

    audio_text = db.Column(db.Text, nullable=True)
    
    # New fields to match SummaryModel
    date_published = db.Column(db.String(100), nullable=True)
    key_points = db.Column(db.JSON)  # Store as JSON array of points
    sections = db.Column(db.JSON)  # Store as JSON array of section objects
    sources = db.Column(db.JSON)  # Store as JSON array of source objects
    newsletter_names = db.Column(db.JSON)  # Store as JSON array of strings
    
    # Relationship with User
    user = db.relationship('User', backref=db.backref('summaries', lazy=True))
    
    # Add this line to existing model
    email_ids = db.Column(db.JSON)  # Store array of email IDs used in summary

    
    def to_text(self) -> str:
        """Get the content of the summary"""
        text = f"Summary from {self.from_date.strftime('%B %d, %Y')} to {self.to_date.strftime('%B %d, %Y')}\n\n"
        
        if self.key_points:
            text += "Key Points:\n"
            for point in self.key_points:
                text += f"  - {point['text']}\n"
            text += "\n"
        
        if self.sections:
            text += "Sections:\n"
            for section in self.sections:
                text += f"Section: {section['header']}\n"
                text += f"{section['content']}\n\n"

        return text
    
    def __str__(self):
        """Convert Summary object to string representation"""
        text = f"Summary from {self.from_date.strftime('%B %d, %Y')} to {self.to_date.strftime('%B %d, %Y')}\n\n"
        
        if self.key_points:
            text += "Key Points:\n"
            for point in self.key_points:
                text += f"  - {point['text']}\n"
            text += "\n"
        
        if self.sections:
            text += "Sections:\n"
            for section in self.sections:
                text += f"Section: {section['header']}\n"
                text += f"{section['content']}\n\n"
        
        if self.sources:
            text += "Sources:\n"
            for source in self.sources:
                text += f"  - {source['title']} ({source['publisher']}, {source['date']}): {source['url']}\n"
            text += "\n"
        
        if self.newsletter_names:
            text += "Newsletters:\n"
            for newsletter_name in self.newsletter_names:
                text += f"  - {newsletter_name}\n"
        
        return text
    def to_dict(self):
        """Convert summary to dictionary format matching SummaryModel"""
        return {
            'date_published': self.date_published,
            'from_date': self.from_date,
            'to_date': self.to_date,
            'key_points': self.key_points or [],
            'sections': self.sections or [],
            'sources': self.sources or [],
            'newsletter_names': self.newsletter_names or []
        }

    @staticmethod
    def from_summary_model(summary_model, user_id):
        """Create Summary instance from SummaryModel"""
        from_date, to_date = summary_model.from_to_date.split(" to ")
        return Summary(
            user_id=user_id,
            date_published=summary_model.date_published,
            from_to_date=summary_model.from_to_date,
            key_points=[point.text for point in summary_model.key_points],
            sections=[{
                'header': section.header,
                'content': section.content
            } for section in summary_model.sections],
            sources=[{
                'url': source.url,
                'date': source.date,
                'title': source.title,
                'publisher': source.publisher
            } for source in summary_model.sources],
            newsletter_names=summary_model.newsletter_names,
            from_date=datetime.strptime(from_date.strip(), '%Y-%m-%d'),
            to_date=datetime.strptime(to_date.strip(), '%Y-%m-%d')
        )

class News(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(500), nullable=False)
    content = db.Column(db.Text, nullable=False)
    
    #topic = db.relationship('Topic', backref='news', lazy=True)

class Topic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    header = db.Column(db.String(500), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    email_id = db.Column(db.Integer, db.ForeignKey('email.id', ondelete='CASCADE'), nullable=False)

    news = db.relationship('News', backref='topic', lazy=True)
    #email = db.relationship('Email', backref='topics', lazy=True)

class Source(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email_id = db.Column(db.Integer, db.ForeignKey('email.id', ondelete='CASCADE'), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    date = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(500), nullable=False)
    publisher = db.Column(db.String(500), nullable=False)

    #email = db.relationship('Email', backref='sources', lazy=True)

class Email(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    unique_identifier = db.Column(db.Text, unique=True, nullable=False)
    name = db.Column(db.Text, nullable=False)  # Newsletter name
    email_date = db.Column(db.DateTime, nullable=False)
    is_excluded = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # Relationships
    topics = db.relationship('Topic', backref='email', lazy=True)
    sources = db.relationship('Source', backref='email', lazy=True)
    user = db.relationship('User', backref=db.backref('emails', lazy=True))

    has_audio = db.Column(db.Boolean, default=False)
    audio_text = db.Column(db.Text, nullable=True)  # New field for storing audio-friendly text

    audio_creation_state = db.Column(db.String(20), default='none')  # Possible values: 'none', 'started', 'completed'

    def to_newsletter(self):
        """Convert the email record to a Newsletter object format"""
        return {
            'name': self.name,
            'topics': [{
                'header': topic.header,
                'summary': topic.summary,
                'news': [{
                    'title': news.title,
                    'content': news.content
                } for news in topic.news]
            } for topic in self.topics],
            # 'sources': [{
            #     'url': source.url,
            #     'date': source.date,
            #     'title': source.title,
            #     'publisher': source.publisher
            # } for source in self.sources]
        }
    
    def to_md(self):
        """ 
        Convert the email to a markdown string 
        """
        email_context = f"""
# {self.name}
*{self.email_date.strftime('%B %d, %Y')}*

## Topics
"""
        for topic in self.topics:
            email_context += f"""
### {topic.header}
{topic.summary}
"""
            if topic.news:
                email_context += "\n#### News\n"
                for news in topic.news:
                    email_context += f"""
- **{news.title}**
  {news.content}
"""
            
            if self.sources:
                email_context += "\n## Sources\n"
                for source in self.sources:
                    email_context += f"""
- [{source.title}]({source.url}) - {source.publisher}, {source.date}
"""
        return email_context

class Newsletter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sender = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    latest_date = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    user = db.relationship('User', backref=db.backref('newsletters', lazy=True))
    def __repr__(self):
        return f'<Newsletter {self.name}>'

class TaskExecution(db.Model):
    """Tracks the execution history of batch tasks"""
    id = db.Column(db.Integer, primary_key=True)
    task_name = db.Column(db.String(100), nullable=False)
    last_success = db.Column(db.DateTime, nullable=True)
    last_attempt = db.Column(db.DateTime, nullable=False, default=datetime.now)
    status = db.Column(db.String(20), nullable=False)  # 'success', 'failed'
    error_message = db.Column(db.Text, nullable=True)
    
    __table_args__ = (
        db.UniqueConstraint('task_name', name='unique_task_name'),
    )
    
    @staticmethod
    def get_last_success(task_name: str) -> datetime | None:
        """Get the timestamp of last successful execution for a task"""
        execution = TaskExecution.query.filter_by(task_name=task_name).first()
        return execution.last_success if execution else None
    
    @staticmethod
    def record_execution(task_name: str, status: str, error_message: str = None):
        """Record a task execution"""
        execution = TaskExecution.query.filter_by(task_name=task_name).first()
        if not execution:
            execution = TaskExecution(task_name=task_name)
        
        execution.last_attempt = datetime.now()
        execution.status = status
        execution.error_message = error_message
        
        if status == 'success':
            execution.last_success = execution.last_attempt
        
        db.session.add(execution)
        db.session.commit()

# Add this new model after the existing models
class AudioFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    data = db.Column(db.LargeBinary, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # Foreign keys for different types of content
    summary_id = db.Column(db.Integer, db.ForeignKey('summary.id', ondelete='CASCADE'), nullable=True)
    email_id = db.Column(db.Integer, db.ForeignKey('email.id', ondelete='CASCADE'), nullable=True)
    
    # Relationships
    summary = db.relationship('Summary', backref=db.backref('audio_file', uselist=False))
    email = db.relationship('Email', backref=db.backref('audio_file', uselist=False))

class Invitation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    invited_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    def __init__(self, email, invited_by_id):
        self.email = email
        self.invited_by_id = invited_by_id
        self.token = secrets.token_urlsafe(32)
        self.expires_at = datetime.utcnow() + timedelta(days=7)  # Invitation expires in 7 days

class ReadStatus(db.Model):
    __tablename__ = 'read_status'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    item_id = db.Column(db.Integer, nullable=False)
    item_type = db.Column(db.String(20), nullable=False)  # 'summary', 'email', or 'newsletter'
    read_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('read_statuses', lazy=True))
    __table_args__ = (
        db.UniqueConstraint('user_id', 'item_id', 'item_type', name='unique_read_status'),
    )

class AsyncProcessingRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email_id = db.Column(db.Integer, db.ForeignKey('email.id', ondelete='CASCADE'), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.now)

    email = db.relationship('Email', backref=db.backref('async_requests', lazy=True))