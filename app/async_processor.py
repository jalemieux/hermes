import threading
from app.audio_processor import process_audio_requests

class AsyncProcessor:
    def __init__(self, app):
        self.app = app
        self.thread = threading.Thread(target=self.run)
        self.thread.daemon = True

    def start(self):
        self.thread.start()

    def run(self):
        with self.app.app_context():
            process_audio_requests() 