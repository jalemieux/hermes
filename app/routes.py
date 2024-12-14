# app/routes.py
from flask import Blueprint, render_template, redirect, url_for, request, flash, session, current_app, jsonify, send_file
from flask_login import login_user, logout_user, login_required, current_user
from openai import OpenAI
from app.mailbox_accessor import MailboxAccessor
from app.models import Newsletter, db, User, Summary, Email
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
        digest_frequency = request.form.get('digest_frequency')

        # Basic validation
        if not email or not password:
            flash('Email and password are required', 'error')
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
        user = User(email=email, digest_frequency=digest_frequency)
        user.set_password(password)
        
        mailbox_accessor = MailboxAccessor()
        inbox_email_address, inbox_id = mailbox_accessor.create_mailbox()
        mailbox_accessor.create_forwarder(inbox_id, user.email)
        
        user.mailslurp_email_address = inbox_email_address
        user.mailslurp_inbox_id = inbox_id

        try:
            db.session.add(user)
            db.session.commit()
            login_user(user)
            #flash('Account created successfully!', 'success')
            return redirect(url_for('main.dashboard'))
        except Exception as e:
            current_app.logger.error(f"Error creating user: {e}")
            db.session.rollback()
            flash('An error occurred. Please try again.', 'error')
            return redirect(url_for('main.signup'))

    return render_template('signup.html')

@main.route('/signin', methods=['GET', 'POST'])
def signin():
    # Clear any existing flash messages at the start of the route
    #session.pop('_flashes', None)
    
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
    # Fetch summaries from the database
    db_summaries = Summary.query.filter_by(user_id=current_user.id, status='completed').order_by(Summary.to_date.desc()).all()
    
    # Convert db summaries to the same format as mock summaries
    db_summaries_formatted = [
        {
            'title': summary.title,
            'start_date': summary.from_date.strftime('%B %d, %Y'),
            'end_date': summary.to_date.strftime('%B %d, %Y'),
            'read_url': url_for('main.read_summary', summary_id=summary.id),
            'type': 'summary',
            'has_audio': summary.has_audio,
        }
        for summary in db_summaries
    ]

    # fetch non-excluded emails from the database
    emails = Email.query.filter_by(
        user_id=current_user.id,
        is_excluded=False  # Add this condition to filter out excluded emails
    ).order_by(Email.created_at.desc()).all()
    
    # Convert db emails to the same format as mock emails
    emails_formatted = [
        {
            'title': email.name,
            'start_date': email.created_at.strftime('%B %d, %Y'),
            'end_date': email.created_at.strftime('%B %d, %Y'),
            'read_url': url_for('main.read_email', email_id=email.id),
            'has_audio': email.has_audio,
            'type': 'email'
        }
        for email in emails
    ]
    
    # Combine and sort by end_date (most recent first)
    combined_summaries = sorted(
        db_summaries_formatted + emails_formatted,
        key=lambda x: datetime.strptime(x['end_date'], '%B %d, %Y'),
        reverse=True
    )
    
    # Get newsletters from the database
    newsletters = Newsletter.query.filter_by(user_id=current_user.id).all()
    #newsletters = Newsletter.query.filter_by(user_id=current_user.id).order_by(Newsletter.latest_date.desc()).all()
    
    return render_template('dashboard.html',
                         mailslurp_email_address=current_user.mailslurp_email_address,
                         user_email=current_user.email,
                         summaries=combined_summaries,
                         email_forwarding_enabled=current_user.email_forwarding_enabled,
                         newsletters=newsletters)

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

@main.route('/oauth2callback')
@login_required
def oauth2callback():
    state = session['state']
    
    flow = create_google_oauth_flow()
    flow.fetch_token(authorization_response=request.url)
    
    credentials = flow.credentials
    
    # Store credentials in user model
    current_user.google_token = credentials.token
    current_user.google_refresh_token = credentials.refresh_token
    current_user.google_token_expiry = datetime.now() + timedelta(seconds=credentials.expiry.second)
    
    db.session.commit()
    
    flash('Gmail access authorized successfully!', 'success')
    return redirect(url_for('main.dashboard'))

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

@main.route('/generate-audio/<int:summary_id>', methods=['POST'])
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
        
    if not summary.audio_filename:
        return jsonify({'error': 'No audio file available'}), 404
        
    audio_path = os.path.join(current_app.config['AUDIO_DIR'], summary.audio_filename)
    
    if not os.path.exists(audio_path):
        return jsonify({'error': 'Audio file not found'}), 404
        
    return send_file(audio_path, mimetype='audio/mpeg')

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
    # Get summary_id from query params if present
    summary_id = request.args.get('summary_id')
    
    if not summary_id:
        flash('No summary ID provided', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Load the summary and its emails
    summary = Summary.query.get(summary_id)
    if not summary or summary.user_id != current_user.id:
        flash('Unauthorized access', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Store the email content in the session for the chat context
    email_ids = [email_id for email_id in summary.email_ids] if summary.email_ids else []
    emails = Email.query.filter(Email.id.in_(email_ids)).all()
    emails_content = ""
    for email in emails:
        emails_content += email.to_md()

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
        {"role": "assistant", "content": "context window: " + emails_content},
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
        
        success = voice_generator.generate_voice_clip_for_email(email_id, audio_path)
        
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
        
    if not email.audio_filename:
        return jsonify({'error': 'No audio file available'}), 404
        
    audio_path = os.path.join(current_app.config['AUDIO_DIR'], email.audio_filename)
    
    if not os.path.exists(audio_path):
        return jsonify({'error': 'Audio file not found'}), 404
        
    return send_file(audio_path, mimetype='audio/mpeg')

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
