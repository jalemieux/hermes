import time
from app.models import db, AsyncProcessingRequest, Email
from app.voice_generator import VoiceClipGenerator
import logging

logging.basicConfig(level=logging.INFO)


def process_audio_requests():
    while True:
        # Fetch pending audio requests
        pending_requests = AsyncProcessingRequest.query.filter_by(status='pending', type='audio').all()

        for request in pending_requests:
            email = Email.query.get(request.email_id)
            if email:
                try:
                    # Update request status to 'started'
                    request.status = 'started'
                    db.session.commit()

                    # Generate audio
                    voice_generator = VoiceClipGenerator()
                    success = voice_generator.email_to_audio(email)

                    # Update request and email status
                    if success:
                        request.status = 'completed'
                        email.has_audio = True
                    else:
                        request.status = 'failed'

                    db.session.commit()
                except Exception as e:
                    logging.error(f"Error processing audio request for email {email.id}: {str(e)}")
                    request.status = 'failed'
                    db.session.commit()

        # Sleep for a while before checking again
        time.sleep(10) 