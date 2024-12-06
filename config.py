import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key'
    
    # PostgreSQL database URL
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://myuser:mypassword@localhost:5432/hermes'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    MAILSLURP_API_KEY = os.environ.get('MAILSLURP_API_KEY')
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    
    # Google OAuth Settings
    GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'http://127.0.0.1:5000/oauth2callback')
    
    # OpenAI Settings
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY') or None
    
    # MailSlurp Settings
    MAILSLURP_API_KEY = os.environ.get('MAILSLURP_API_KEY') or None
    
    ELEVEN_LABS_API_KEY = os.environ.get('ELEVEN_LABS_API_KEY') or None  # Replace with your actual API key
    ELEVEN_LABS_VOICE_ID = "nPczCjzI2devNBz1zQrb"  # Replace with your preferred voice ID
    VOICE_GENERATOR = "openai"
