from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from flask import current_app
import os

def create_google_oauth_flow():
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": current_app.config['GOOGLE_CLIENT_ID'],
                "client_secret": current_app.config['GOOGLE_CLIENT_SECRET'],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [current_app.config['GOOGLE_REDIRECT_URI']]
            }
        },
        scopes=[
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/userinfo.email'
        ]
    )
    flow.redirect_uri = current_app.config['GOOGLE_REDIRECT_URI']
    return flow

def credentials_from_user(user):
    if not user.google_token:
        return None
        
    return Credentials(
        token=user.google_token,
        refresh_token=user.google_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=current_app.config['GOOGLE_CLIENT_ID'],
        client_secret=current_app.config['GOOGLE_CLIENT_SECRET'],
        scopes=['https://www.googleapis.com/auth/gmail.readonly']
    )