from datetime import datetime, timedelta
import logging

from pydantic import BaseModel
from app import create_app
from app.mailbox_accessor import MailboxAccessor
from app.models import AudioFile, News, Source, Topic, User, Summary, db, TaskExecution, Newsletter, Email
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
        # Get all emails that don't have audio yet
        pending_emails = Email.query.join(
            Newsletter, 
            Email.name == Newsletter.name
        ).filter(
            Email.has_audio == False,
            Email.is_excluded == False,
            Newsletter.is_active == True,
            Email.created_at > datetime.now() - timedelta(days=1)
        ).all()
        
        logger.info(f"Found {len(pending_emails)} emails pending audio generation: {', '.join([pending_email.name for pending_email in pending_emails])}")
        
        voice_generator = VoiceClipGenerator()
        for email in pending_emails:
            voice_generator.email_to_audio(email)


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

        
        for user in users:
            try:
                summary_generator = SummaryGenerator()
                summary_generator.process_inbox_emails(user.id, start_date=datetime.now() - timedelta(days=1))
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
                    
                    for email in emails:
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

def recreate_newsletters_from_inbox():
    """
    Task to recreate Newsletter records based on email sender addresses from inbox.
    This task:
    1. Gets all users with mailboxes
    2. For each user, fetches emails from their inbox
    3. Creates Newsletter records based on unique sender addresses
    4. Replaces existing newsletter records for the user
    """
    app = create_app()
    
    with app.app_context():
        logger.info("Starting recreate_newsletters_from_inbox task")
        
        try:
            users = User.query.filter(User.mailslurp_inbox_id.isnot(None)).all()
            mailbox_accessor = MailboxAccessor()
            
            for user in users:
                try:
                    logger.info(f"Processing user {user.id}")
                    inbox_id = user.mailslurp_inbox_id
                    
                    # Fetch emails from last 30 days
                    emails = mailbox_accessor.get_emails_from_last_n_days(inbox_id, 30)
                    logger.info(f"Found {len(emails)} emails for user {user.id}")
                    
                    # Get unique senders and their latest emails
                    sender_map = {}
                    for email in emails:
                        sender = email.sender.name
                        if sender not in sender_map or email.created_at > sender_map[sender]['date']:
                            sender_map[sender] = {
                                'date': email.created_at,
                                'subject': email.subject, 
                                'from': email.sender.raw_value
                            }
                    
                    # Delete existing newsletters for this user
                    Newsletter.query.filter_by(user_id=user.id).delete()
                    
                    # Create new newsletter records
                    for sender, info in sender_map.items():
                        newsletter = Newsletter(
                            user_id=user.id,
                            name=sender,  # Using sender email as newsletter name
                            subject=info['from'],
                            is_active=True,
                            sender=sender,
                            latest_date=info['date']
                        )
                        db.session.add(newsletter)
                        logger.info(f"Created newsletter record for sender: {sender}")
                    
                    db.session.commit()
                    
                except Exception as e:
                    logger.error(f"Error processing user {user.id}: {str(e)}")
                    db.session.rollback()
                    continue
            
            TaskExecution.record_execution('recreate_newsletters_from_inbox', 'success')
            logger.info("Successfully completed recreate_newsletters_from_inbox task")
            
        except Exception as e:
            logger.error(f"Error in recreate_newsletters_from_inbox: {str(e)}")
            TaskExecution.record_execution('recreate_newsletters_from_inbox', 'failed', str(e))
            raise e

def delete_emails_without_audio():
    """
    Delete emails that have no audio files associated with them.
    This task:
    1. Finds all emails where has_audio is False
    2. Deletes them from the database
    3. Records the execution status
    """
    app = create_app()
    
    with app.app_context():
        logger.info("Starting delete_emails_without_audio task")
        
        try:
            # Find emails without audio
            emails_to_delete = Email.query.filter_by(has_audio=False).all()
            count = len(emails_to_delete)
            logger.info(f"Found {count} emails without audio")
            
            # Load related data for logging purposes
            for email in emails_to_delete:
                topics = Topic.query.filter_by(email_id=email.id).all()
                logger.info(f"Will delete {len(topics)} topics for email {email.id}")
                for topic in topics:
                    news_items = News.query.filter_by(topic_id=topic.id).all()
                    logger.info(f"Will delete {len(news_items)} news items for topic {topic.id}")
                    for news_item in news_items:
                        db.session.delete(news_item)
                        logger.info(f"Deleted news item {news_item.id}")
                    db.session.commit()
                    logger.info(f"Deleted topic {topic.id}")
                    db.session.delete(topic)
                    db.session.commit()
                
                sources = Source.query.filter_by(email_id=email.id).all()
                logger.info(f"Will delete {len(sources)} sources for email {email.id}")
                for source in sources:
                    db.session.delete(source)
                    logger.info(f"Deleted source {source.id}")
                logger.info(f"Will delete {len(sources)} sources for email {email.id}")
                
                db.session.delete(email)
                logger.info(f"Deleted email {email.id}")
            
            
            
            TaskExecution.record_execution('delete_emails_without_audio', 'success')
            logger.info(f"Successfully deleted {count} emails without audio")
            
        except Exception as e:
            db.session.rollback()
            TaskExecution.record_execution('delete_emails_without_audio', 'failed', str(e))
            raise e

def print_last_email(user_id):
    """
    Fetch and print attributes of the last email received for a given user.
    
    Args:
        user_id: The ID of the user whose inbox should be checked
    """
    app = create_app()
    
    with app.app_context():
        try:
            # Get user and verify mailbox exists
            user = User.query.get(user_id)
            if not user or not user.mailslurp_inbox_id:
                logger.error(f"User {user_id} not found or has no mailbox configured")
                return False
            
            mailbox = MailboxAccessor()
            
            # Fetch emails from last day to ensure we get the latest
            emails = mailbox.get_emails_from_last_n_days(user.mailslurp_inbox_id, 1)
            
            if not emails:
                logger.info("No emails found in the last 24 hours")
                return False
            
            # Get the last email (most recent)
            last_email = emails[-1]
            
            # Print all attributes of the email object using dir()
            logger.info("All attributes of the email object:")
            for attr in dir(last_email):
                # Skip internal/private attributes that start with _
                if not attr.startswith('_'):
                    try:
                        value = getattr(last_email, attr)
                        # Convert value to string and truncate if too long
                        if isinstance(value, str) and len(value) > 200:
                            value = value[:200] + "..."
                        logger.info(f"{attr}: {value}")
                    except Exception as e:
                        logger.info(f"{attr}: <Error accessing attribute: {str(e)}>")

            
            
            return True
            
        except Exception as e:
            logger.error(f"Error in print_last_email: {str(e)}")
            return False

def list_users():
    """
    List all users in the system with their IDs and email addresses.
    """
    app = create_app()
    
    with app.app_context():
        try:
            users = User.query.all()
            
            if not users:
                logger.info("No users found in the system")
                return False
            
            logger.info("\nUser List:")
            logger.info("-" * 50)
            logger.info(f"{'ID':<6} {'Email':<30} {'Has Mailbox':<12}")
            logger.info("-" * 50)
            
            for user in users:
                has_mailbox = "Yes" if user.mailslurp_inbox_id else "No"
                logger.info(f"{user.id:<6} {user.email:<30} {has_mailbox:<12}")
            
            logger.info("-" * 50)
            logger.info(f"Total users: {len(users)}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error in list_users: {str(e)}")
            return False

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
        print("- recreate_newsletters_from_inbox")
        print("- delete_emails_without_audio")
        print("- print_last_email")
        print("- list_users")
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
    elif task_name == "recreate_newsletters_from_inbox":
        recreate_newsletters_from_inbox()
    elif task_name == "delete_emails_without_audio":
        delete_emails_without_audio()
    elif task_name == "print_last_email":
        if len(sys.argv) < 3:
            print("Please provide a user_id as argument")
            print("Usage: python -m app.tasks print_last_email <user_id>")
            sys.exit(1)
        user_id = int(sys.argv[2])
        print_last_email(user_id)
    elif task_name == "list_users":
        list_users()
    else:
        print(f"Unknown task: {task_name}")
        print("Available tasks:")
        print("- daily_summaries")
        print("- generate_email_audio")
        print("- process_inbox_emails")
        print("- identify_newsletter_name")
        print("- create_newsletters_from_emails")
        print("- recreate_newsletters_from_inbox")
        print("- delete_emails_without_audio")
        print("- print_last_email")
        print("- list_users")
        sys.exit(1)