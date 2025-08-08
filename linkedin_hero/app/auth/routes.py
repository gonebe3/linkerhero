from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import User
from app import db, login_manager
from .forms import LoginForm, RegistrationForm
from authlib.integrations.flask_client import OAuth
import os

# Blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/')

# OAuth setup (will be initialized in app factory)
oauth = OAuth()

def get_or_create_oauth_user(info):
    email = info["email"]
    user = User.query.filter_by(email=email).first()
    if user:
        # Link Google if not already
        if user.provider != 'google':
            user.provider = 'google'
            user.provider_id = info.get('sub')
            db.session.commit()
        return user
    # Create new user
    user = User(
        email=email,
        username=info.get('name') or email.split('@')[0],
        provider='google',
        provider_id=info.get('sub'),
        is_active=True
    )
    db.session.add(user)
    db.session.commit()
    return user

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.password_hash and check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=form.remember_me.data)
            user.last_login = db.func.now()
            db.session.commit()
            flash('Logged in successfully!', 'success')
            return redirect(url_for('main.dashboard'))
        else:
            flash('Invalid email or password.', 'error')
    return render_template('auth/login.html', form=form)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    form = RegistrationForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered.', 'error')
        elif User.query.filter_by(username=form.username.data).first():
            flash('Username already taken.', 'error')
        else:
            user = User(
                email=form.email.data,
                username=form.username.data,
                password_hash=generate_password_hash(form.password.data),
                provider='email',
                is_active=True
            )
            db.session.add(user)
            db.session.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('auth.login'))
    return render_template('auth/register.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('main.index'))

@auth_bp.route('/auth/google')
def google_login():
    # Placeholder for Google OAuth - will implement with Authlib
    flash('Google OAuth will be implemented in Phase 2.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/auth/google/callback')
def google_callback():
    # Placeholder for Google OAuth callback
    flash('Google OAuth will be implemented in Phase 2.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile')
@login_required
def profile():
    return render_template('auth/profile.html') 