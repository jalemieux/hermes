# app/routes.py
from flask import Blueprint, render_template, redirect, url_for, request, flash, session, current_app, jsonify, send_file
from flask_login import login_user, logout_user, login_required, current_user
from openai import OpenAI
from app.mailbox_accessor import MailboxAccessor
from app.models import Newsletter, db, User, Summary, Email, AudioFile, Invitation
#from app.utils.oauth import create_google_oauth_flow, credentials_from_user
from app.oauth import create_google_oauth_flow
from datetime import datetime, timedelta
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
import re
import mailslurp_client
import random
import logging
import os
from werkzeug.utils import secure_filename
import io

from app.summary_generator import SummaryGenerator
from app.voice_generator import VoiceClipGenerator
from app.email_sender import EmailSender
logging.basicConfig(level=logging.DEBUG)


main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template('index.html')

@main.route('/about')
def about():
    return render_template('about.html')

@main.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        invitation_token = request.form.get('invitation_token')

        # Basic validation
        if not email or not password:
            flash('Email and password are required', 'error')
            return redirect(url_for('main.signup'))

        # Check invitation
        invitation = Invitation.query.filter_by(token=invitation_token, email=email, used=False).first()
        if not invitation or invitation.expires_at < datetime.utcnow():
            flash('Invalid or expired invitation', 'error')
            return redirect(url_for('main.signup'))

        # Email format validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            flash('Please enter a valid email address', 'error')
            return redirect(url_for('main.signup'))

        # Check if user already exists
        if User.query.filter_by(email=email).first():
            flash('Email address already registered, please sign in.', 'error')
            return redirect(url_for('main.signin', email=email))

        # Create new user
        user = User(email=email)
        user.set_password(password)
        
        mailbox_accessor = MailboxAccessor()
        inbox_email_address, inbox_id = mailbox_accessor.create_mailbox()
        mailbox_accessor.create_forwarder(inbox_id, user.email)
        
        user.mailslurp_email_address = inbox_email_address
        user.mailslurp_inbox_id = inbox_id

        # Mark invitation as used
        invitation.used = True

        try:
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash('Account created successfully!', 'success')
            return redirect(url_for('main.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while creating your account.', 'error')
            return redirect(url_for('main.signup'))

    # For GET request, check if there's an invitation token
    invitation_token = request.args.get('token')
    email = request.args.get('email')
    
    if invitation_token:
        invitation = Invitation.query.filter_by(token=invitation_token, email=email, used=False).first()
        if invitation and invitation.expires_at > datetime.utcnow():
            return render_template('signup.html', invitation_token=invitation_token, email=email)
    
    # If no valid invitation, show invitation-only message
    return render_template('signup.html', invitation_required=True)

@main.route('/signin', methods=['GET', 'POST'])
def signin():
    # Clear any existing flash messages at the start of the route
    session.pop('_flashes', None)
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember_me') else False

        if not email or not password:
            flash('Please enter both email and password', 'error')
            return redirect(url_for('main.signin'))

        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user, remember=remember)
            # Get the next page from the URL parameters, defaulting to dashboard
            next_page = request.args.get('next', url_for('main.dashboard'))
            # Don't flash success message anymore
            return redirect(next_page)
        current_app.logger.error(f"Invalid email or password for user {email}")
        flash('Invalid email or password', 'error')
        return render_template('signin.html')

    return render_template('signin.html')

@main.route('/signout')
@login_required
def signout():
    logout_user()
    #flash('Successfully signed out', 'success')
    return redirect(url_for('main.index'))

@main.route('/dashboard')
@login_required
def dashboard():
    # Get the current page number from the query string, default to 1
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Number of items per page

    # Fetch summaries from the database with pagination
    db_summaries = Summary.query.filter_by(user_id=current_user.id, status='completed') \
                                .order_by(Summary.to_date.desc()) \
                                .paginate(page=page, per_page=per_page, error_out=False)

    # Convert db summaries to the same format as mock summaries
    db_summaries_formatted = [
        {
            'title': summary.title,
            'start_date': summary.from_date.strftime('%B %d, %Y'),
            'end_date': summary.to_date.strftime('%B %d, %Y'),
            'read_url': url_for('main.read_summary', summary_id=summary.id),
            'type': 'summary',
            'has_audio': summary.has_audio,
            'id': summary.id
        }
        for summary in db_summaries.items
    ]

    # Fetch non-excluded emails from the database with pagination
    emails = Email.query.filter_by(user_id=current_user.id, is_excluded=False) \
                        .order_by(Email.created_at.desc()) \
                        .paginate(page=page, per_page=per_page, error_out=False)

    # Convert db emails to the same format as mock emails
    emails_formatted = [
        {
            'title': email.name,
            'start_date': email.created_at.strftime('%B %d, %Y'),
            'end_date': email.created_at.strftime('%B %d, %Y'),
            'read_url': url_for('main.read_email', email_id=email.id),
            'has_audio': email.has_audio,
            'type': 'email',
            'id': email.id
        }
        for email in emails.items
    ]

    # Combine and sort by end_date (most recent first)
    combined_summaries = sorted(
        db_summaries_formatted + emails_formatted,
        key=lambda x: datetime.strptime(x['end_date'], '%B %d, %Y'),
        reverse=True
    )

    # Get newsletters from the database
    newsletters = Newsletter.query.filter_by(user_id=current_user.id).all()

    return render_template('dashboard.html',
                           mailslurp_email_address=current_user.mailslurp_email_address,
                           user_email=current_user.email,
                           summaries=combined_summaries,
                           email_forwarding_enabled=current_user.email_forwarding_enabled,
                           newsletters=newsletters,
                           page=page,
                           total_pages=max(db_summaries.pages, emails.pages))

@main.route('/authorize-gmail')
@login_required
def authorize_gmail():
    flow = create_google_oauth_flow()
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    session['state'] = state
    return redirect(authorization_url)



@main.route('/generate-summary', methods=['POST'])
@login_required
def generate_summary():
    try:
        # Clear any existing flash messages
        session.pop('_flashes', None)
        
        # ensure not previous summary is being generated
        five_minutes_ago = datetime.now() - timedelta(minutes=5)
        recent_pending_summaries = Summary.query.filter(
            Summary.user_id == current_user.id,
            Summary.status == 'pending',
            Summary.created_at >= five_minutes_ago
        ).all()
        
        if recent_pending_summaries:
            return jsonify({
                'status': 'error',
                'message': 'A summary is already being generated. Please wait a few minutes and try again.'
            }), 400
        
        # Create a new summary record with status 'pending'
        new_summary = Summary(
            user_id=current_user.id,
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

        try:
            summary_generator = SummaryGenerator()
            new_summary = summary_generator.generate_summary(current_user.id, new_summary)
        except Exception as e:
            current_app.logger.error(f"Summary generation failed: {str(e)}")
            Summary.query.filter_by(id=new_summary.id).delete()
            db.session.commit()
            return jsonify({
                'status': 'error',
                'message': f'Failed to generate summary. Please try again. {e}'
            }), 400

        db.session.add(new_summary)
        db.session.commit()
        

        
        # If successful
        return jsonify({
            'status': 'success',
            'message': 'New summary generated successfully!'
        }), 200
    except Exception as e:
        current_app.logger.error(f"Summary generation failed: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to generate summary. Please try again. {e}'
        }), 400

@main.route('/summary/<int:summary_id>')
@login_required
def read_summary(summary_id):
    # Fetch the summary from database
    summary = Summary.query.get(summary_id)
    if not summary:
        flash('Summary not found', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Create the summary dictionary with the same structure as the mock
    summary_json = {
        'id': summary.id,
        'title': summary.title,
        'start_date': summary.from_date.strftime('%B %d, %Y'),
        'end_date': summary.to_date.strftime('%B %d, %Y'),
        'source_count': len(summary.sources) if summary.sources else 0,
        'has_audio': summary.has_audio,
        'key_points': [point["text"] for point in summary.key_points] if summary.key_points else [],
        'sections': [
            {
                'title': section['header'],
                'content': section['content']
            }
            for section in summary.sections
        ] if summary.sections else [],
        'sources': [
            {
                'title': source['title'],
                'publication': source['publisher'],
                'date': source['date'],
                'url': source['url']
            }
            for source in summary.sources
        ] if summary.sources else []
    }
    
    return render_template('summary.html', summary=summary_json)

@main.route('/audio/summary/<int:summary_id>')
@login_required
def listen_summary(summary_id):
    # Fetch the summary from database
    summary_obj = Summary.query.get(summary_id)
    if not summary_obj:
        flash('Summary not found', 'error')
        return redirect(url_for('main.dashboard'))

    if not summary_obj.has_audio:
        flash('No audio available for this summary', 'error')
        return redirect(url_for('main.dashboard'))
    
    template_data = {
        'title': summary_obj.title,
        'date': summary_obj.to_date.strftime('%B %d, %Y'),
        'back_url': url_for('main.read_summary', summary_id=summary_obj.id),
        'audio_url': url_for('main.get_audio_file', summary_id=summary_obj.id),
        'sections': [
            {
                'header': section['header'],
                'content': section['content']
            }
            for section in summary_obj.sections
        ] if summary_obj.sections else []
    }
    
    return render_template('audio.html', **template_data)

@main.route('/summary/<int:summary_id>/emails')
@login_required
def summary_emails(summary_id):
    # Fetch the summary
    summary = Summary.query.get(summary_id)
    if not summary:
        flash('Summary not found', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Fetch all emails used in this summary
    email_ids = [email_id for email_id in summary.email_ids] if summary.email_ids else []
    emails = Email.query.filter(Email.id.in_(email_ids)).all()
    
    summary_json = {
        'id': summary.id,
        'title': summary.title,
        'start_date': summary.from_date.strftime('%B %d, %Y'),
        'end_date': summary.to_date.strftime('%B %d, %Y'),
    }
    
    return render_template('summary_emails.html', summary=summary_json, emails=emails)
@main.route('/generate-audio/email/<int:email_id>', methods=['POST'])
@login_required
def generate_audio_email(email_id):
    try:

        # fetch email by id
        email = Email.query.get(email_id)
        if not email:
            return jsonify({'status': 'error', 'message': 'Email not found'}), 404
        
        voice_generator = VoiceClipGenerator()
        success = voice_generator.email_to_audio(email)

        if success:
            return jsonify({
                'status': 'success',
                'message': 'Audio generated successfully'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to generate audio'
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Audio generation failed: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to generate audio: {str(e)}'
        }), 400


@main.route('/generate-audio/summary/<int:summary_id>', methods=['POST'])
@login_required
def generate_audio(summary_id):
    try:
        # Create the /var/data directory if it doesn't exist
        os.makedirs('/var/data/audio', exist_ok=True)
        
        voice_generator = VoiceClipGenerator()
        audio_filename = f'summary_{summary_id}_{int(datetime.now().timestamp())}.mp3'
        audio_path = os.path.join(current_app.config['AUDIO_DIR'], audio_filename)
        
        success = voice_generator.generate_voice_clip(summary_id, audio_path)
        
        if success:
            # Update the summary with the audio filename
            summary = Summary.query.get(summary_id)
            summary.audio_filename = audio_filename
            summary.has_audio = True
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Audio generated successfully'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to generate audio'
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Audio generation failed: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to generate audio: {str(e)}'
        }), 400

@main.route('/email-forwarder', methods=['POST'])
@login_required
def email_forwarder():
    try:
        # Get the currently logged in user
        user = User.query.get(current_user.get_id())
        if not user:
            flash('User not found', 'error')
            return redirect(url_for('main.dashboard'))
        
        inbox_id = user.mailslurp_inbox_id
        user_email = user.email
        
        if not inbox_id or not user_email:
            flash('Missing required parameters', 'error')
            return redirect(url_for('main.dashboard'))
        
        # Check if the checkbox was checked in the form
        new_state = request.form.get('email_forwarding') == 'on'
        
        try:
            mailbox = MailboxAccessor()
            if new_state:
                mailbox.create_forwarder(inbox_id, user_email)
                message = 'Email forwarding enabled'
            else:
                mailbox.remove_forwarder(inbox_id)
                message = 'Email forwarding disabled'
            
            # Update the user's forwarding state
            current_user.email_forwarding_enabled = new_state
            db.session.commit()
            
            flash(message, 'success')
        except Exception as e:
            flash(str(e), 'error')
            
    except Exception as e:
        flash(str(e), 'error')
        
    return redirect(url_for('main.dashboard'))

@main.route('/audio-file/<int:summary_id>')
@login_required
def get_audio_file(summary_id):
    summary = Summary.query.get_or_404(summary_id)
    
    # Verify the summary belongs to the current user
    if summary.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    audio_file = AudioFile.query.filter_by(summary_id=summary_id).first()
    if not audio_file:
        return jsonify({'error': 'No audio file available'}), 404
    
    return send_file(
        io.BytesIO(audio_file.data),
        mimetype='audio/mpeg',
        as_attachment=True,
        download_name=audio_file.filename
    )

@main.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            token = user.generate_reset_token()
            reset_link = url_for('main.reset_password', token=token, _external=True)
            
            # Send reset link via email using Gmail SMTP
            try:
                email_sender = EmailSender()
                email_sender.send_email(
                    to_email=user.email,
                    subject="Reset Your Password - Hermes",
                    body=f"""
                    Hello,
                    
                    You recently requested to reset your password. Click the link below to set a new password:
                    
                    {reset_link}
                    
                    This link will expire in 1 hour. If you didn't request this reset, please ignore this email.
                    
                    Best regards,
                    Hermes Team
                    """
                )
                flash('Password reset instructions have been sent to your email.', 'success')
            except Exception as e:
                current_app.logger.error(f"Error sending reset email: {e}")
                flash('An error occurred while sending the reset email. Please try again.', 'error')
            
        else:
            # Don't reveal if email exists or not
            flash('If an account exists with this email, you will receive password reset instructions.', 'success')
        
        return redirect(url_for('main.signin'))
    
    return render_template('forgot_password.html')

@main.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    # Find user by reset token
    user = User.query.filter_by(reset_token=token).first()
    
    if not user or not user.verify_reset_token(token):
        flash('Invalid or expired reset link. Please request a new one.', 'error')
        return redirect(url_for('main.forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not password or not confirm_password:
            flash('Please enter both password fields.', 'error')
            return redirect(url_for('main.reset_password', token=token))
            
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('main.reset_password', token=token))
        
        # Update password and clear reset token
        user.set_password(password)
        user.clear_reset_token()
        
        flash('Your password has been reset successfully. Please sign in.', 'success')
        return redirect(url_for('main.signin'))
    
    return render_template('reset_password.html')

@main.route('/chat')
@login_required
def chat():
    # Get IDs from query params
    summary_id = request.args.get('summary_id')
    email_id = request.args.get('email_id')
    
    if not summary_id and not email_id:
        flash('No content ID provided', 'error')
        return redirect(url_for('main.dashboard'))
    
    if summary_id:
        # Load the summary and its emails
        summary = Summary.query.get(summary_id)
        if not summary or summary.user_id != current_user.id:
            flash('Unauthorized access', 'error')
            return redirect(url_for('main.dashboard'))
        
        # Get content from summary's emails
        email_ids = [email_id for email_id in summary.email_ids] if summary.email_ids else []
        emails = Email.query.filter(Email.id.in_(email_ids)).all()
        content = ""
        for email in emails:
            content += email.to_md()
            
    else:
        # Load single email
        email = Email.query.get(email_id)
        if not email or email.user_id != current_user.id:
            flash('Unauthorized access', 'error')
            return redirect(url_for('main.dashboard'))
        
        content = email.to_md()

    prompt = """
You are an AI assistant. You will receive a context window containing various pieces of information
that may or may not be relevant to the user's query. The user will ask you a question. You should
answer the user's question using only the information contained in the context window. If the 
answer cannot be determined from the context, respond with: "I'm sorry, but I don't have enough
information to answer that." Do not invent details, and do not provide information that is not 
supported by the context window. If the user's question requires an explanation, use the relevant
data from the context window to support your response. You must not provide any information that
is not present or cannot be clearly inferred from the context window.
    """
    
    # Add initial welcome message
    initial_message = "Hello! I'm here to help you understand the content of this summary. What would you like to know?"
    
    session['chat_messages'] = [
        {"role": "system", "content": prompt},
        {"role": "assistant", "content": "context window: " + content},
        {"role": "assistant", "content": initial_message}  # Add the welcome message
    ]
    
    return render_template('chat.html', initial_message=initial_message)  # Pass to template

@main.route('/chat/send', methods=['POST'])
@login_required
def chat_send():
    try:
        message = request.json.get('message')
        if not message:
            return jsonify({
                'status': 'error',
                'message': 'No message provided'
            }), 400

        messages = session.get('chat_messages', [])
        if not messages:
            return jsonify({
                'status': 'error',
                'message': 'No email context available'
            }), 400
        current_app.logger.info(f"Chat messages: {messages}")

        messages.append({"role": "user", "content": message})   
        openai_client = OpenAI()
        completion = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
        )
        
        # Here you would process the message and generate a response
        # For now, we'll just echo it back with a mock delay
        response = completion.choices[0].message.content
        messages.append({"role": "assistant", "content": response})
        session['chat_messages'] = messages
        
        return jsonify({
            'status': 'success',
            'message': response
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Chat processing failed: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to process message. Please try again.'
        }), 400

@main.route('/email/<int:email_id>')
@login_required
def read_email(email_id):
    # Fetch the email from database
    email = Email.query.get_or_404(email_id)
    
    # Verify the email belongs to the current user
    if email.user_id != current_user.id:
        flash('Unauthorized access', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('email.html', email=email)

@main.route('/generate-audio/email/<int:email_id>', methods=['POST'])
@login_required
def generate_email_audio(email_id):
    try:
        # Create the /var/data directory if it doesn't exist
        os.makedirs('/var/data/audio', exist_ok=True)
        
        voice_generator = VoiceClipGenerator()
        audio_filename = f'email_{email_id}_{int(datetime.now().timestamp())}.mp3'
        audio_path = os.path.join(current_app.config['AUDIO_DIR'], audio_filename)
        
        success = voice_generator.generate_voice_clip(email_id, audio_path)
        
        if success:
            # Update the email with the audio filename
            email = Email.query.get(email_id)
            email.audio_filename = audio_filename
            email.has_audio = True
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Audio generated successfully'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to generate audio'
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Audio generation failed: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to generate audio: {str(e)}'
        }), 400

@main.route('/audio/email/<int:email_id>')
@login_required
def listen_email(email_id):
    email = Email.query.get_or_404(email_id)
    
    # Verify the email belongs to the current user
    if email.user_id != current_user.id:
        flash('Unauthorized access', 'error')
        return redirect(url_for('main.dashboard'))
        
    if not email.has_audio:
        flash('No audio available for this email', 'error')
        return redirect(url_for('main.dashboard'))

    template_data = {
        'title': email.name,
        'date': email.email_date.strftime('%B %d, %Y'),
        'back_url': url_for('main.read_email', email_id=email.id),
        'audio_url': url_for('main.get_audio_file_email', email_id=email.id),
        'email': email
    }
    
    return render_template('audio.html', **template_data)

@main.route('/audio-file/email/<int:email_id>')
@login_required
def get_audio_file_email(email_id):
    email = Email.query.get_or_404(email_id)
    
    # Verify the email belongs to the current user
    if email.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    audio_file = AudioFile.query.filter_by(email_id=email_id).first()
    if not audio_file:
        return jsonify({'error': 'No audio file available'}), 404
    
    return send_file(
        io.BytesIO(audio_file.data),
        mimetype='audio/mpeg',
        as_attachment=True,
        download_name=audio_file.filename
    )

@main.route('/api/newsletter/<int:newsletter_id>/toggle', methods=['POST'])
@login_required
def toggle_newsletter(newsletter_id):
    newsletter = Newsletter.query.get_or_404(newsletter_id)
    
    # Verify the newsletter belongs to the current user
    if newsletter.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        # Toggle the is_active status
        newsletter.is_active = not newsletter.is_active
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': f'Newsletter {"activated" if newsletter.is_active else "deactivated"} successfully',
            'is_active': newsletter.is_active
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@main.route('/exclude-newsletter', methods=['POST'])
@login_required
def exclude_newsletter():
    newsletter_id = request.form.get('newsletter_id')
    if not newsletter_id:
        flash('Newsletter ID is required', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # Update the email record to mark it as excluded
        email = Email.query.filter_by(
            user_id=current_user.id,
            id=newsletter_id,
            is_excluded=False
        ).first()
        
        if email:
            email.is_excluded = True
            db.session.commit()
            flash(f'Successfully excluded "{email.name}" from your feed', 'success')
        else:
            flash('Newsletter not found or already excluded', 'error')
            
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while excluding the newsletter', 'error')
        
    return redirect(url_for('main.dashboard'))

@main.route('/invite', methods=['GET', 'POST'])
@login_required
def invite():
    if request.method == 'POST':
        email = request.form.get('email')
        
        if not email:
            flash('Email address is required', 'error')
            return redirect(url_for('main.invite'))
            
        # Check if email already registered
        if User.query.filter_by(email=email).first():
            flash('This email is already registered', 'error')
            return redirect(url_for('main.invite'))
            
        # Check if invitation already exists
        existing_invitation = Invitation.query.filter_by(email=email, used=False).first()
        if existing_invitation:
            flash('An invitation has already been sent to this email', 'error')
            return redirect(url_for('main.invite'))
            
        # Create new invitation
        invitation = Invitation(email=email, invited_by_id=current_user.id)
        
        try:
            db.session.add(invitation)
            db.session.commit()
            
            # Send invitation email
            invitation_url = url_for('main.signup', token=invitation.token, email=email, _external=True)
            email_sender = EmailSender()
            email_sender.send_email(
                to_email=email,
                subject="You're invited to join Hermes",
                body=f"""
                Hello,
                
                You've been invited to join Hermes! Click the link below to create your account:
                
                {invitation_url}
                
                This invitation will expire in 7 days.
                
                Best regards,
                Hermes Team
                """
            )
            
            flash('Invitation sent successfully', 'success')
            return redirect(url_for('main.invite'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while sending the invitation', 'error')
            return redirect(url_for('main.invite'))
            
    return render_template('invite.html')

@main.route('/connect/gmail')
@login_required
def connect_gmail():
    """Start Gmail OAuth flow"""
    flow = create_google_oauth_flow()
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    session['state'] = state
    return redirect(authorization_url)

@main.route('/oauth2callback')
@login_required
def oauth2callback():
    """Handle Gmail OAuth callback"""
    flow = create_google_oauth_flow()
    flow.fetch_token(
        authorization_response=request.url,
        state=session['state']
    )
    credentials = flow.credentials
    current_user.update_gmail_credentials(credentials)
    
    # After successful connection, redirect to newsletter selection
    return redirect(url_for('main.select_newsletters'))

@main.route('/select-newsletters')
@login_required
def select_newsletters():
    """Show available newsletters for selection"""
    if not current_user.gmail_credentials:
        flash('Please connect your Gmail account first', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Get available newsletters
    newsletters = get_gmail_newsletters(current_user)
    selected = current_user.selected_newsletters or []
    
    return render_template(
        'select_newsletters.html',
        newsletters=newsletters,
        selected=selected
    )

@main.route('/api/newsletters/update', methods=['POST'])
@login_required
def update_selected_newsletters():
    """Update user's selected newsletters"""
    data = request.get_json()
    selected = data.get('selected', [])
    
    # Validate selection against daily limit
    if len(selected) > Config.MAX_NEWSLETTERS_PER_DAY:
        return jsonify({
            'status': 'error',
            'message': f'Maximum {Config.MAX_NEWSLETTERS_PER_DAY} newsletters allowed'
        }), 400
    
    current_user.selected_newsletters = selected
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'message': 'Newsletter preferences updated'
    })
