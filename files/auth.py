from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, current_user, login_required
from files.models import db, User

# Blueprint for authentication routes (signup, login, logout)
auth_bp = Blueprint('auth', __name__, template_folder='templates')

@auth_bp.route('/signup', methods=['GET','POST'])
def signup():
    """
    Handle user registration.
    - GET: render the signup form.
    - POST: validate input, create new User, hash password, and redirect to login.
    """
    
    # If already logged in, send back to home
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        email = request.form['email']
        pw    = request.form['password']
        # Prevent duplicate registrations
        if User.query.filter_by(email=email).first():
            flash('Email already registered')
            return redirect(url_for('auth.signup'))
        # Create and store new user
        new = User(email=email,
                   password=generate_password_hash(pw),
                   is_admin=False)
        db.session.add(new)
        db.session.commit()
        flash('Account created—please log in')
        return redirect(url_for('auth.login'))
    # Render signup template on GET
    return render_template('signup.html')

@auth_bp.route('/login', methods=['GET','POST'])
def login():
    """
    Handle user login.
    - GET: render the login form.
    - POST: authenticate credentials and log the user in.
    """
    
    # If already logged in, send back to home
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        email = request.form['email']
        pw    = request.form['password']
        user  = User.query.filter_by(email=email).first()
        # Verify credentials
        if not user or not check_password_hash(user.password, pw):
            flash('Invalid credentials')
            return redirect(url_for('auth.login'))
        # Log the user in and redirect home
        login_user(user)
        return redirect(url_for('main.index'))
    # Render login template on GET
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    # Log the current user out and clear any flash messages.
    logout_user()
    # Clear any leftover flash messages
    session.pop('_flashes', None)
    return redirect(url_for('main.index'))
