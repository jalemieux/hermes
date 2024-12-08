from datetime import datetime, timedelta
import logging
from app import create_app
from app.models import User, Summary, db
from app.summary_generator import SummaryGenerator
from app.email_sender import EmailSender
from flask import url_for

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
                    raise e
                    # Clean up failed summary
                    if new_summary:
                        db.session.delete(new_summary)
                        db.session.commit()
                    continue
                    
        except Exception as e:
            logger.error(f"Error in generate_daily_summaries: {str(e)}")
            raise e
            

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Please provide a task name as argument")
        # Print supported tasks when no arguments provided
        print("Available tasks:")
        print("- daily_summaries")
        sys.exit(1)
    
    task_name = sys.argv[1]
    
    if task_name == "daily_summaries":
        generate_daily_summaries()
    else:
        print(f"Unknown task: {task_name}")
        print("Available tasks:")
        print("- daily_summaries")
        sys.exit(1)