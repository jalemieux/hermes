# app/models.py
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime
import json

db = SQLAlchemy()

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

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Summary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    content = db.Column(db.Text)
    status = db.Column(db.String(100), default='pending')
    title = db.Column(db.String(200))
    has_audio = db.Column(db.Boolean, default=False)
    audio_url = db.Column(db.String(500))
    from_date = db.Column(db.DateTime, nullable=False)
    to_date = db.Column(db.DateTime, nullable=False)
    
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

    def to_dict(self):
        """Convert summary to dictionary format matching SummaryModel"""
        return {
            'date_published': self.date_published,
            'from_to_date': self.from_to_date,
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
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=False)
    title = db.Column(db.String(500), nullable=False)
    content = db.Column(db.Text, nullable=False)
    
    #topic = db.relationship('Topic', backref='news', lazy=True)

class Topic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    header = db.Column(db.String(500), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    email_id = db.Column(db.Integer, db.ForeignKey('email.id'), nullable=False)

    news = db.relationship('News', backref='topic', lazy=True)
    #email = db.relationship('Email', backref='topics', lazy=True)

class Source(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email_id = db.Column(db.Integer, db.ForeignKey('email.id'), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    date = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(500), nullable=False)
    publisher = db.Column(db.String(500), nullable=False)

    #email = db.relationship('Email', backref='sources', lazy=True)

class Email(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    unique_identifier = db.Column(db.Text, unique=True, nullable=False)
    name = db.Column(db.Text, nullable=False)  # Newsletter name
    email_date = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    topics = db.relationship('Topic', backref='email', lazy=True)
    sources = db.relationship('Source', backref='email', lazy=True)
    user = db.relationship('User', backref=db.backref('emails', lazy=True))

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