
# app/routes.py
from flask import Blueprint, render_template, redirect, url_for, request

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
        # Handle form submission
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        digest_frequency = request.form.get('digest_frequency')
        # Add your user registration logic here
        return redirect(url_for('dashboard'))
    return render_template('signup.html')
