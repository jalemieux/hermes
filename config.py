import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Google OAuth Settings
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'http://127.0.0.1:5000/oauth2callback')
    
    # OpenAI Settings
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    
    # MailSlurp Settings
    MAILSLURP_API_KEY = os.environ.get('MAILSLURP_API_KEY') or '9f2c4fd3d243e31a0086d86fe8c59019613bc29d952e87c8729ed650b25c755c'
    
    ELEVEN_LABS_API_KEY = "sk_5152d17d53f5a0d36407190ae3daee31a40d6310ec230790"  # Replace with your actual API key
    ELEVEN_LABS_VOICE_ID = "nPczCjzI2devNBz1zQrb"  # Replace with your preferred voice ID
    VOICE_GENERATOR = "openai"
