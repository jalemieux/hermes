# run.py

from datetime import datetime
import logging

from sqlalchemy import JSON, Column
from app import create_app
from app.mailbox_accessor import MailboxAccessor
from app.models import Summary, User, db
from app.summary_generator import SummaryGenerator, test_fetch_emails, test_process_emails, test_synthesize_newsletter
from config import Config


app = create_app()

logging.basicConfig(level=logging.INFO)

def create_user_mailbox(user_id):
    user = User.query.get(user_id)
        
    mailbox_accessor = MailboxAccessor()
    inbox_email_address, inbox_id = mailbox_accessor.create_mailbox()
        
    user.mailslurp_email_address = inbox_email_address
    user.mailslurp_inbox_id = inbox_id
    
    db.session.add(user)
    db.session.commit()


def test_email_forwarder(user_id):
    user = User.query.get(user_id)
    mailbox_accessor = MailboxAccessor()
    ret = mailbox_accessor.create_forwarder(user.mailslurp_inbox_id, user.email)
    print(ret)

import elevenlabs

def eleven_labs_synthesize_summary(summary_id):
    from elevenlabs import ElevenLabs

    client = ElevenLabs(
        api_key="sk_5152d17d53f5a0d36407190ae3daee31a40d6310ec230790",
    )
    data = client.text_to_speech.convert(
        voice_id="nPczCjzI2devNBz1zQrb",
        model_id="eleven_turbo_v2",
        text="Hello ... ... ... anyone htere? I'm just testing the --- --- voice generation / / /  and pauses", 
        voice_settings=elevenlabs.VoiceSettings(
            stability=0.2,
            similarity_boost=0.1
        )
    )
    from typing import Iterator

    file_path = "output.mp3"
    with open(file_path, 'wb') as file:  # Open the file in binary write mode
        for chunk in data:
            file.write(chunk)  # Write each chunk from the iterator

def re_generate_summary(summary_id):
    new_summary = Summary.query.get(summary_id)
    email_ids = new_summary.email_ids

    summary_generator = SummaryGenerator()
    summary, sources, newsletter_names = summary_generator.synthesis(email_ids)
    logging.info(f"Synthesized summary {summary}")
        
    new_summary.title = summary.title
    new_summary.date_published = datetime.now()
    new_summary.key_points = [{"text": point.text} for point in summary.key_points]
    new_summary.sections = [{"header": section.header, "content": section.content} for section in summary.sections]
    db.session.add(new_summary)
    db.session.commit()

def re_generate_summary_audio(summary_id):
    from app.voice_generator import VoiceClipGenerator
    voice_generator = VoiceClipGenerator()
    voice_generator.generate_voice_clip(summary_id)
    

if __name__ == '__main__':
    #app.run(debug=True)
    with app.app_context():
        #create_user_mailbox(1)
        #re_generate_summary(3)
        #eleven_labs_synthesize_summary(3)
        #re_generate_summary_audio(1)
        test_email_forwarder(1)