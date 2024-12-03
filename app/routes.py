# app/routes.py
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from app.models import db, User
import re

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
    return render_template('dashboard.html', email_address=current_user.email)
