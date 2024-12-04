# app/models.py
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    digest_frequency = db.Column(db.String(20), default='daily')
    
    # Add Google OAuth fields
    google_token = db.Column(db.String(500))
    google_refresh_token = db.Column(db.String(500))
    google_token_expiry = db.Column(db.DateTime)
    
    # Add MailSlurp fields
    mailslurp_email_address = db.Column(db.String(120))
    mailslurp_inbox_id = db.Column(db.String(120))
    
    # Add relationship to summaries
    #summaries = db.relationship('Summary', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Summary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    content = db.Column(db.Text)
    title = db.Column(db.String(200))
    has_audio = db.Column(db.Boolean, default=False)
    audio_url = db.Column(db.String(500))
    from_date = db.Column(db.DateTime, nullable=False)
    to_date = db.Column(db.DateTime, nullable=False)
    
    # Relationship with User
    user = db.relationship('User', backref=db.backref('summaries', lazy=True))

class Email(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    unique_identifier = db.Column(db.String(100), unique=True, nullable=False)
    email_text = db.Column(db.Text, nullable=False)
    email_date = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with User
    user = db.relationship('User', backref=db.backref('emails', lazy=True))