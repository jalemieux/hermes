from datetime import datetime, timedelta
import logging

from pydantic import BaseModel
from app import create_app
from app.mailbox_accessor import MailboxAccessor
from app.models import User, Summary, db, TaskExecution, Newsletter, Email
from app.summary_generator import SummaryGenerator
from app.email_sender import EmailSender
from flask import url_for
from app.voice_generator import VoiceClipGenerator
from app.models import Email
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_daily_summaries():
    """
    Generate summaries for all active users and notify them by email.
    This function is meant to be called daily by a cron job.
    """
    app = create_app()
    
    with app.app_context():
        try:
            users = User.query.filter(User.mailslurp_inbox_id.isnot(None)).all()
            logger.info(f"Found {len(users)} users with mailslurp inboxes")
            
            summary_generator = SummaryGenerator()
            email_sender = EmailSender()
            
            for user in users:
                try:
                    logger.info(f"Generating summary for user {user.id}")
                    new_summary = None
                    
                    # Create a new pending summary
                    new_summary = Summary(
                        user_id=user.id,
                        title="",
                        content="",
                        from_date=datetime.now(),
                        to_date=datetime.now(),
                        status='pending',
                        has_audio=False
                    )
                    db.session.add(new_summary)
                    db.session.commit()
                    db.session.refresh(new_summary)
                    
                    # Generate the summary
                    summary_generator.generate_summary(user.id, new_summary)
                    logger.info(f"Successfully generated summary for user {user.id}")
                    
                    # Send email notification
                    summary_url = url_for('main.summary', summary_id=new_summary.id, _external=True)
                    email_body = f"""
Hello!

Your daily news summary is ready. Here's what we've gathered for you:

Title: {new_summary.title}
Period: {new_summary.to_date}

You can read your full summary here:
{summary_url}

Best regards,
Hermes Team
                    """
                    
                    email_sender.send_email(
                        to_email=user.email,
                        subject=f"Your Daily News Summary: {new_summary.title}",
                        body=email_body
                    )
                    logger.info(f"Notification email sent to user {user.id}")
                    
                except Exception as e:
                    logger.error(f"Error generating summary for user {user.id}: {str(e)}")
                    # Clean up failed summary
                    if new_summary:
                        db.session.delete(new_summary)
                        db.session.commit()
                    continue
            
            # Record successful execution
            TaskExecution.record_execution('generate_daily_summaries', 'success')
                    
        except Exception as e:
            logger.error(f"Error in generate_daily_summaries: {str(e)}")
            TaskExecution.record_execution('generate_daily_summaries', 'failed', str(e))
            raise e
            



def generate_email_audio():
    """
    Generate audio versions of emails that don't have audio yet.
    This function:
    1. Finds all emails without audio
    2. Converts their content to an audio-friendly format
    3. Generates audio files using text-to-speech
    4. Updates the email records with audio file info
    """
    app = create_app()
    
    with app.app_context():
        try:
            # Get all emails that don't have audio yet
            pending_emails = Email.query.join(
                Newsletter, 
                Email.name == Newsletter.name
            ).filter(
                Email.has_audio == False,
                Email.is_excluded == False,
                Newsletter.is_active == True
            ).all()
            
            logger.info(f"Found {len(pending_emails)} emails pending audio generation: {", ".join([pending_email.name for pending_email in pending_emails])}")
            
            summary_generator = SummaryGenerator()
            voice_generator = VoiceClipGenerator()
            
            for email in pending_emails:
                try:
                    # Convert email content to audio-friendly format
                    audio_text = summary_generator.convert_to_audio_format(email.to_md())
                    
                    # Generate unique filename
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    audio_filename = f"newsletter_{email.id}_{timestamp}.mp3"
                    audio_path = os.path.join(app.config['AUDIO_DIR'], audio_filename)
                    
                    # Generate audio file
                    success = voice_generator.openai_text_to_speech(audio_path, audio_text, content_type="email")
                    
                    if success:
                        # Update email record
                        email.audio_filename = audio_filename
                        email.has_audio = True
                        db.session.commit()
                        logger.info(f"Generated audio for email {email.id}")
                    
                except Exception as e:
                    logger.error(f"Error generating audio for email {email.id}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in generate_email_audio task: {str(e)}")



def process_inbox_emails():
    """
    Process new emails from users' inboxes and store their content in the database.
    This function is meant to be called periodically by a scheduler.
    
    The function:
    1. Gets all users with configured mailboxes
    2. For each user, fetches new emails from their inbox
    3. Processes each email to extract newsletter content
    4. Stores the processed content in the database
    5. Updates task execution status and records any failures
    """
    app = create_app()
    
    with app.app_context():
        failures = 0

        task_execution = TaskExecution.query.filter_by(task_name='process_inbox_emails').first()
        if not task_execution:
            task_execution = TaskExecution(task_name='process_inbox_emails', status='started', last_success=datetime.now() - timedelta(days=3))
            db.session.add(task_execution)
            db.session.commit()
            db.session.refresh(task_execution)
       
        users = User.query.filter(User.mailslurp_inbox_id.isnot(None)).all()
        
        task_execution.status = 'started'
        db.session.commit()
        db.session.refresh(task_execution)

        last_run = task_execution.last_success or datetime.now() - timedelta(days=3)
        for user in users:
            try:
                summary_generator = SummaryGenerator()
                summary_generator.process_inbox_emails(user.id, start_date=last_run)
            except Exception as e:
                logger.error(f"Error processing user {user.id}: {str(e)}")
                failures += 1
                continue
            
        # Record successful execution
        TaskExecution.record_execution('process_inbox_emails', 'success' if failures == 0 else 'failed')
        
        

def identify_newsletter_name():
    """
    Process emails to identify newsletter names.
    This function is meant to be called when needed to identify newsletter names.
    """
    app = create_app()
    
    with app.app_context():
        try:
            users = User.query.filter(User.mailslurp_inbox_id.isnot(None)).all()
            logger.info(f"Found {len(users)} users with mailslurp inboxes")
            
            summary_generator = SummaryGenerator()
            mailbox_accessor = MailboxAccessor()
            
            for user in users:
                try:
                    inbox_id = user.mailslurp_inbox_id
                    
                    # Fetch recent emails
                    emails = mailbox_accessor.get_emails_from_last_n_days(inbox_id, 7)
                    logger.info(f"Found {len(emails)} emails for user {user.id}")
                    
                    for email in emails[:2]:
                        try:
                            # Get newsletter name for each email
                            newsletter_info = summary_generator.newsletter_name(email)
                            logger.info(f"Identified newsletter: {newsletter_info.newsletter_name} for email from {email._from}")
                            
                        except Exception as e:
                            logger.error(f"Error identifying newsletter for email: {str(e)}")
                            failures += 1
                            continue
                            
                except Exception as e:
                    logger.error(f"Error processing user {user.id}: {str(e)}")
                    failures += 1
                    continue
                    
            TaskExecution.record_execution('identify_newsletter_name', 'success' if failures == 0 else 'failed')
            
        except Exception as e:
            logger.error(f"Error in identify_newsletter_name: {str(e)}")
            TaskExecution.record_execution('identify_newsletter_name', 'failed', str(e))
            raise e

def create_newsletters_from_emails():
    """
    Task to create Newsletter records from existing Email records.
    This task looks for emails without corresponding newsletter records and creates them.
    """
    app = create_app()
    
    with app.app_context():
        logging.info("Starting create_newsletters_from_emails task")
            
        try:
            users = User.query.filter(User.mailslurp_inbox_id.isnot(None)).all()
            for user in users:
                # get unqieu email name from all emails for a given user
                emails = Email.query.distinct(
                    Email.name
                ).filter(
                    Email.user_id == user.id
                ).all()

                for email in emails:
                    logging.info(f"Processing email: {email.name}")
                    # Skip if newsletter already exists
                    existing_newsletter = Newsletter.query.filter_by(
                        user_id=user.id,
                        name=email.name
                    ).first()
                    
                    if not existing_newsletter:
                        logging.info(f"Creating new newsletter record: {email.name}")
                        newsletter = Newsletter(
                            user_id=user.id,
                            name=email.name,
                            is_active=True,
                            sender="Unknown",
                            latest_date=datetime.now()
                        )
                        db.session.add(newsletter)
                    else:
                        logging.debug(f"Newsletter already exists: {email.name}")
                        
            
            db.session.commit()
            logging.info("Successfully completed create_newsletters_from_emails task")
            return True
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error in create_newsletters_from_emails task: {str(e)}")
            raise

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Please provide a task name as argument")
        print("Available tasks:")
        print("- daily_summaries")
        print("- generate_email_audio")
        print("- process_inbox_emails")
        print("- identify_newsletter_name")
        print("- create_newsletters_from_emails")
        sys.exit(1)
    
    task_name = sys.argv[1]
    
    if task_name == "daily_summaries":
        generate_daily_summaries()
    elif task_name == "generate_email_audio":
        generate_email_audio()
    elif task_name == "process_inbox_emails":
        process_inbox_emails()
    elif task_name == "identify_newsletter_name":
        identify_newsletter_name()
    elif task_name == "create_newsletters_from_emails":
        create_newsletters_from_emails()
    else:
        print(f"Unknown task: {task_name}")
        print("Available tasks:")
        print("- daily_summaries")
        print("- generate_email_audio")
        print("- process_inbox_emails")
        print("- identify_newsletter_name")
        print("- create_newsletters_from_emails")
        sys.exit(1)