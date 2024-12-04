# app/routes.py
from flask import Blueprint, render_template, redirect, url_for, request, flash, session, current_app, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app.models import db, User, Summary
#from app.utils.oauth import create_google_oauth_flow, credentials_from_user
from app.oauth import create_google_oauth_flow
from datetime import datetime, timedelta
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
import re
import mailslurp_client
import random


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
        
        # create a mailslurp configuration
        configuration = mailslurp_client.Configuration()
        configuration.api_key['x-api-key'] = "9f2c4fd3d243e31a0086d86fe8c59019613bc29d952e87c8729ed650b25c755c"
        with mailslurp_client.ApiClient(configuration) as api_client:
            # create an inbox
            inbox_controller = mailslurp_client.InboxControllerApi(api_client)
            inbox = inbox_controller.create_inbox()
            #inbox =  {'created_at': datetime.datetime(2024, 12, 4, 0, 30, 45, 251000, tzinfo=tzutc()),
            #  'description': None,
            #  'domain_id': None,
            #  'email_address': '3981e2bb-e8b5-4012-a82f-a6c409a17fc6@mailslurp.biz',
            #  'expires_at': '2024-12-05T12:30:45.242Z',
            #  'favourite': False,
            #  'functions_as': None,
            #  'id': '3981e2bb-e8b5-4012-a82f-a6c409a17fc6',
            #  'inbox_type': 'HTTP_INBOX',
            #  'name': None,
            #  'read_only': False,
            #  'tags': [],
            #  'user_id': '2ffa1a89-3cf2-4542-ac20-9dcb2f33a09c',
            #  'virtual_inbox': False}
        # Add the MailSlurp inbox email_address and id to the user table as MailSlurp attributes
        user.mailslurp_email_address = inbox.email_address
        user.mailslurp_inbox_id = inbox.id

        try:
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash('Account created successfully!', 'success')
            return redirect(url_for('main.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred. Please try again.', 'error')
            return redirect(url_for('main.signup'))

    return render_template('signup.html')

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
            flash('Successfully signed in!', 'success')
            return redirect(next_page)
        
        flash('Invalid email or password', 'error')
        return redirect(url_for('main.signin'))

    return render_template('signin.html')

@main.route('/signout')
@login_required
def signout():
    logout_user()
    flash('Successfully signed out', 'success')
    return redirect(url_for('main.index'))

@main.route('/dashboard')
@login_required
def dashboard():
    mock_summaries = [
        {
            'title': 'Tech Industry Weekly Roundup',
            'start_date': 'March 11, 2024',
            'end_date': 'March 18, 2024',
            'read_url': url_for('main.read_summary', summary_id=1),
            'has_audio': True,
            'audio_url': url_for('main.listen_summary', summary_id=1)
        },
        {
            'title': 'Climate Change Policy Updates',
            'start_date': 'March 10, 2024',
            'end_date': 'March 17, 2024',
            'read_url': url_for('main.read_summary', summary_id=2),
            'has_audio': True,
            'audio_url': url_for('main.listen_summary', summary_id=2)
        },
        {
            'title': 'Global Economic Outlook',
            'start_date': 'March 9, 2024',
            'end_date': 'March 16, 2024',
            'read_url': url_for('main.read_summary', summary_id=3),
            'has_audio': False,
            'audio_url': None
        }
    ]
    # Fetch summaries from the database
    db_summaries = Summary.query.filter_by(user_id=current_user.id).order_by(Summary.to_date.desc()).all()
    
    # Convert db summaries to the same format as mock summaries
    db_summaries_formatted = [
        {
            'title': summary.title,
            'start_date': summary.from_date.strftime('%B %d, %Y'),
            'end_date': summary.to_date.strftime('%B %d, %Y'),
            'read_url': url_for('main.read_summary', summary_id=summary.id),
            'has_audio': summary.has_audio,
            'audio_url': url_for('main.listen_summary', summary_id=summary.id) if summary.has_audio else None
        }
        for summary in db_summaries
    ]
    
    # Combine mock summaries and db summaries
    combined_summaries = db_summaries_formatted + mock_summaries
    
    # Sort combined summaries by end_date (most recent first)
    combined_summaries.sort(key=lambda x: datetime.strptime(x['end_date'], '%B %d, %Y'), reverse=True)
    
    return render_template('dashboard.html',
                         summaries=combined_summaries,
                         mailslurp_email_address=current_user.mailslurp_email_address)

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
    current_user.google_token_expiry = datetime.utcnow() + timedelta(seconds=credentials.expiry.second)
    
    db.session.commit()
    
    flash('Gmail access authorized successfully!', 'success')
    return redirect(url_for('main.dashboard'))

@main.route('/generate-summary', methods=['POST'])
@login_required
def generate_summary():
    try:
        # Clear any existing flash messages
        session.pop('_flashes', None)
        # Get the timestamp of the last summary generation
        last_summary = Summary.query.filter_by(user_id=current_user.id).order_by(Summary.created_at.desc()).first()
        start_time = last_summary.to_date if last_summary else datetime.now() - timedelta(days=7)
        import time
        time.sleep(3)
        import random

        # if random.random() < 0.5:
        #     raise Exception("Randomly generated error for testing purposes")
        # Generate a random summary
        summary_title = "Weekly Tech News"
        summary_content = "This week in tech, several major events took place. OpenAI announced a new version of their AI model, GPT-5, which has shown significant improvements in natural language understanding and generation. Apple released their latest product, the Vision Pro, which has received positive reviews from both critics and consumers. Tesla has announced plans to build a new Gigafactory in Texas, which is expected to create thousands of new jobs. Microsoft has completed its acquisition of Activision Blizzard, making it one of the largest gaming companies in the world."

        # Create a new summary object
        new_summary = Summary(
            user_id=current_user.id,
            title=summary_title,
            content=summary_content,
            from_date=start_time,
            to_date=datetime.now(),
            has_audio=False  # Assuming no audio for the random summary
        )

        # Add the new summary to the database
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
    # Mock summary data for testing
    summary = {
        'id': summary_id,
        'title': 'Tech Industry Weekly Roundup',
        'start_date': 'March 11, 2024',
        'end_date': 'March 18, 2024',
        'source_count': 12,
        'has_audio': True,
        'key_points': [
            'OpenAI announced GPT-5 with breakthrough capabilities in reasoning and multimodal understanding',
            'Apple\'s mixed reality headset Vision Pro surpassed 1 million sales in its first quarter',
            'Tesla revealed plans for a new affordable electric vehicle model starting at $25,000',
            'Microsoft completed its acquisition of Activision Blizzard for $69 billion'
        ],
        'sections': [
            {
                'title': 'AI Developments',
                'content': '''
                <p>This week saw major developments in artificial intelligence, led by OpenAI's surprise announcement of GPT-5. 
                The new model demonstrates significant improvements in reasoning capabilities and can now process multiple types 
                of input, including images, audio, and video, with unprecedented accuracy.</p>
                
                <p>Google and Microsoft also made significant AI-related announcements, with both companies introducing new 
                enterprise-focused AI solutions. Google's new AI Platform aims to simplify machine learning workflows, while 
                Microsoft expanded its Azure AI services with new customization options.</p>
                '''
            },
            {
                'title': 'Hardware and Devices',
                'content': '''
                <p>Apple's Vision Pro continues to exceed expectations, with analysts noting strong developer adoption and 
                consumer interest despite the high price point. The company's shares reached a new all-time high following 
                the sales announcement.</p>
                
                <p>Tesla's announcement of a new affordable model has been met with enthusiasm from both investors and 
                potential customers. The company claims the new vehicle will maintain Tesla's high standards for range and 
                performance while achieving a significantly lower price point through manufacturing innovations.</p>
                '''
            }
        ],
        'sources': [
            {
                'title': 'OpenAI Unveils GPT-5: A New Era in Artificial Intelligence',
                'publication': 'TechCrunch',
                'date': 'March 15, 2024',
                'url': 'https://techcrunch.com/example'
            },
            {
                'title': 'Vision Pro Sales Exceed Expectations in First Quarter',
                'publication': 'Bloomberg',
                'date': 'March 14, 2024',
                'url': 'https://bloomberg.com/example'
            },
            {
                'title': 'Tesla Announces $25,000 Electric Vehicle',
                'publication': 'Reuters',
                'date': 'March 12, 2024',
                'url': 'https://reuters.com/example'
            }
        ]
    }
    
    return render_template('summary.html', summary=summary)

@main.route('/audio/<int:summary_id>')
@login_required
def listen_summary(summary_id):
    # Mock summary data for testing
    summary = {
        'id': summary_id,
        'title': 'Tech Industry Weekly Roundup',
        'start_date': 'March 11, 2024',
        'end_date': 'March 18, 2024',
        'audio_url': '/static/audio/episode4.mp3',  # You'll need to add a sample audio file
        'has_audio': True
    }
    
    if not summary['has_audio']:
        flash('No audio available for this summary', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('audio.html', summary=summary)
