from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user

main_bp = Blueprint('main', __name__, url_prefix='/')

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('main/dashboard.html')

@main_bp.route('/pricing')
def pricing():
    # Placeholder: implement pricing page and waitlist form
    return '<h1>Pricing Page (Coming Soon)</h1>'

@main_bp.route('/waitlist', methods=['POST'])
def waitlist():
    # Placeholder: implement waitlist logic
    email = request.form.get('email')
    if not email:
        flash('Please enter a valid email.', 'error')
        return redirect(url_for('main.pricing'))
    # Add to waitlist logic here
    flash('You have been added to the waitlist!', 'success')
    return redirect(url_for('main.pricing')) 