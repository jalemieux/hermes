import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key'
    
    # Gmail SMTP Settings
    GMAIL_SENDER_EMAIL = os.environ.get('GMAIL_SENDER_EMAIL')
    GMAIL_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD')
    
    
    # PostgreSQL database URL
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
    'postgresql://myuser:mypassword@localhost:5432/hermes'
        #'postgresql://wordsnapdb1_user:gR2GogwlUciUHCFbWL0q1mXq6fcxKeP2@dpg-crtjmfbtq21c73ft4tug-a.oregon-postgres.render.com/hermes'
        ##
    #

    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    MAILSLURP_API_KEY = os.environ.get('MAILSLURP_API_KEY')
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET') 
    
    # Google OAuth Settings
    GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'http://hermes.samrtlayer.ventures/oauth2callback')
    
    # OpenAI Settings
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY') or None
    
    # MailSlurp Settings
    MAILSLURP_API_KEY = os.environ.get('MAILSLURP_API_KEY') or None
    
    ELEVEN_LABS_API_KEY = os.environ.get('ELEVEN_LABS_API_KEY') or None  # Replace with your actual API key
    ELEVEN_LABS_VOICE_ID = "nPczCjzI2devNBz1zQrb"  # Replace with your preferred voice ID
    VOICE_GENERATOR = "openai"
    INCLUDE_KEY_POINTS = "false"
    
    # For generating absolute URLs
    SERVER_NAME = os.environ.get('SERVER_NAME', 'localhost:5000')
    AUDIO_DIR = os.environ.get('AUDIO_DIR', '/Users/jac/Dev/src/hermes/app/static/audio')
    MAX_NEWSLETTERS_PER_DAY = 5  # Adjust as needed

