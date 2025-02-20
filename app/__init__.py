
import threading
import time
from flask import Flask
from flask_login import LoginManager
from config import Config
from app.models import db, User
import os

login_manager = LoginManager()

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))






def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'main.signin'
    
    # Create database tables
    with app.app_context():
        if os.getenv('RESET_DB') == 'true':
            db.drop_all()
        db.create_all()
    
    # Register blueprints
    from app.routes import main
    app.register_blueprint(main)
    
    # Start the AsyncProcessor for background processing
    from app.async_processor import AsyncProcessor
    async_processor = AsyncProcessor(app)
    async_processor.start()
    
    
    return app