from datetime import datetime, timedelta
import threading
import time
from app.email_processor import EmailProcessor
from app.models import Summary, User, db

class AsyncSummaryPruner:
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
                
                # Clean up summaries older than 10 days
                ten_days_ago = datetime.now() - timedelta(days=10)
                old_summaries = Summary.query.filter(Summary.user_id == user.id, Summary.to_date < ten_days_ago).all()
                for summary in old_summaries:
                    # Delete audio files associated with the summary
                    if summary.audio_file:
                        db.session.delete(summary.audio_file)
                    db.session.delete(summary)
                db.session.commit()

            
            time.sleep(3600)

class AsyncEmailProcessor:
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