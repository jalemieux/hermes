import threading
import time
from app.email_processor import EmailProcessor
from app.models import User

class AsyncProcessor:
    def __init__(self, app):
        self.app = app
        self.thread = threading.Thread(target=self.run)
        self.thread.daemon = True

    def start(self):
        self.thread.start()

    def run(self):
        with self.app.app_context():
            email_processor = EmailProcessor()
            #process_audio_requests() 
            for user in User.query.all():
                email_processor.process_user_emails(user.id)

            
            time.sleep(300)
