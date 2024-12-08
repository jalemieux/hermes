from datetime import datetime
import logging
from flask import current_app, Flask
from app.models import Summary, User, db
from app.voice_generator import VoiceClipGenerator
from app.summary_generator import SummaryGenerator
from app.mailbox_accessor import MailboxAccessor
from app.email_sender import EmailSender
from config import Config
from elevenlabs import ElevenLabs, client, VoiceSettings
from typing import Iterator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_user_mailbox(user_id):
    """Create a mailbox for a user using MailSlurp."""
    user = User.query.get(user_id)
    if not user:
        logger.error(f"User {user_id} not found")
        return False
        
    mailbox_accessor = MailboxAccessor()
    inbox_email_address, inbox_id = mailbox_accessor.create_mailbox()
        
    user.mailslurp_email_address = inbox_email_address
    user.mailslurp_inbox_id = inbox_id
    
    db.session.add(user)
    db.session.commit()
    return True


def test_email_forwarder(user_id):
    """Test email forwarding setup for a user."""
    user = User.query.get(user_id)
    if not user:
        logger.error(f"User {user_id} not found")
        return False
        
    mailbox_accessor = MailboxAccessor()
    ret = mailbox_accessor.create_forwarder(user.mailslurp_inbox_id, user.email)
    logger.info(f"Email forwarder creation result: {ret}")
    return ret


def test_send_email():
    """Test email sending functionality."""
    app = Flask(__name__)
    app.config.from_object(Config)
    
    with app.app_context():
        try:
            email_sender = EmailSender()
            success = email_sender.send_email(
                to_email="jalemieux@gmail.com",  # Replace with your test email
                subject="Test Email from Hermes",
                body="""
                Hello!
                
                This is a test email from the Hermes password reset system.
                
                If you received this email, the Gmail SMTP configuration is working correctly.
                
                Best regards,
                Hermes Team
                """
            )
            
            if success:
                logger.info("✅ Email sent successfully!")
            return success
            
        except Exception as e:
            logger.error(f"❌ Failed to send email: {str(e)}")
            raise e


def eleven_labs_synthesize_summary(summary_id):
    """Generate voice synthesis using ElevenLabs API."""
    try:
        api_key = current_app.config['ELEVENLABS_API_KEY']
        voice_id = current_app.config['ELEVENLABS_VOICE_ID']
        
        summary = Summary.query.get(summary_id)
        if not summary:
            logger.error(f"Summary {summary_id} not found")
            return False

        text = summary.get_formatted_text()  # Implement this method in Summary model
        client = ElevenLabs(api_key=api_key)
        audio = client.text_to_speech.convert(
            voice_id=voice_id,
            model_id="eleven_turbo_v2",
            text=text,
            voice_settings=VoiceSettings(
                stability=0.2,
                similarity_boost=0.1
            )
        )

        file_path = f"summaries/audio/{summary_id}.mp3"
        with open(file_path, 'wb') as file:
            file.write(audio)
        
        return True

    except Exception as e:
        logger.error(f"Error generating voice synthesis: {str(e)}")
        return False


def re_generate_summary(summary_id):
    """
    Regenerate an existing summary while keeping the same email sources.
    
    Args:
        summary_id: ID of the summary to regenerate
    """
    try:
        new_summary = Summary.query.get(summary_id)
        if not new_summary:
            logger.error(f"Summary {summary_id} not found")
            return False
            
        email_ids = new_summary.email_ids
        logger.info(f"Regenerating summary {summary_id} with {len(email_ids)} emails")

        summary_generator = SummaryGenerator()
        summary, sources, newsletter_names = summary_generator.synthesis(email_ids)
        logger.info(f"Synthesized summary {summary}")
            
        new_summary.title = summary.title
        new_summary.date_published = datetime.now()
        new_summary.key_points = [{"text": point.text} for point in summary.key_points]
        new_summary.sections = [{"header": section.header, "content": section.content} for section in summary.sections]
        db.session.add(new_summary)
        db.session.commit()
        
        logger.info(f"Successfully regenerated summary {summary_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error regenerating summary {summary_id}: {str(e)}")
        return False


def re_generate_summary_audio(summary_id):
    """
    Regenerate the audio for an existing summary.
    
    Args:
        summary_id: ID of the summary to regenerate audio for
    """
    try:
        voice_generator = VoiceClipGenerator()
        voice_generator.generate_voice_clip(summary_id)
        logger.info(f"Successfully regenerated audio for summary {summary_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error regenerating audio for summary {summary_id}: {str(e)}")
        return False


if __name__ == "__main__":
    import sys
    from app import create_app
    
    app = create_app()
    
    if len(sys.argv) < 2:
        print("Please provide a tool name and required arguments")
        print("Available tools:")
        print("- regenerate_summary <summary_id>")
        print("- regenerate_audio <summary_id>")
        print("- create_mailbox <user_id>")
        print("- test_forwarder <user_id>")
        print("- test_email")
        print("- synthesize_summary <summary_id>")
        sys.exit(1)
    
    tool_name = sys.argv[1]
    
    with app.app_context():
        if tool_name == "regenerate_summary":
            if len(sys.argv) < 3:
                print("Please provide a summary_id")
                sys.exit(1)
            summary_id = int(sys.argv[2])
            re_generate_summary(summary_id)
            
        elif tool_name == "regenerate_audio":
            if len(sys.argv) < 3:
                print("Please provide a summary_id")
                sys.exit(1)
            summary_id = int(sys.argv[2])
            re_generate_summary_audio(summary_id)
            
        elif tool_name == "create_mailbox":
            if len(sys.argv) < 3:
                print("Please provide a user_id")
                sys.exit(1)
            user_id = int(sys.argv[2])
            create_user_mailbox(user_id)
            
        elif tool_name == "test_forwarder":
            if len(sys.argv) < 3:
                print("Please provide a user_id")
                sys.exit(1)
            user_id = int(sys.argv[2])
            test_email_forwarder(user_id)
            
        elif tool_name == "test_email":
            test_send_email()
            
        elif tool_name == "synthesize_summary":
            if len(sys.argv) < 3:
                print("Please provide a summary_id")
                sys.exit(1)
            summary_id = int(sys.argv[2])
            eleven_labs_synthesize_summary(summary_id)
            
        else:
            print(f"Unknown tool: {tool_name}")
            print("Available tools:")
            print("- regenerate_summary <summary_id>")
            print("- regenerate_audio <summary_id>")
            print("- create_mailbox <user_id>")
            print("- test_forwarder <user_id>")
            print("- test_email")
            print("- synthesize_summary <summary_id>")
            sys.exit(1) 