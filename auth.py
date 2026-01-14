from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, current_user , login_required
from models import User , PdfHistory
import os
from flask import current_app
from extensions import db, login_manager


auth_bp = Blueprint('auth', __name__)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@auth_bp.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('upload.index'))
        else:
            flash('Invalid username or password', 'danger')
    return render_template('login.html')

@auth_bp.route('/signup', methods=['POST'])
def signup():
    username = request.form['username']
    email = request.form['email']
    password = generate_password_hash(request.form['password'])

    if User.query.filter_by(username=username).first():
        flash('Username already exists', 'danger')
        return redirect(url_for('auth.login'))

    new_user = User(username=username, email=email, password=password)
    db.session.add(new_user)
    db.session.commit()
    flash('Account created! Please log in.', 'success')
    return redirect(url_for('auth.login'))

@auth_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    return render_template('settings.html')


@auth_bp.route('/update-profile', methods=['POST'])
@login_required
def update_profile():
    new_email = request.form.get('email', '').strip()
    new_username = request.form.get('username', '').strip()

    
    if not new_email:
        flash('Email cannot be empty', 'danger')
        return redirect(url_for('auth.settings'))
    
    if new_email == current_user.email and new_username == current_user.username :
        flash('No changes made', 'info')
        return redirect(url_for('auth.settings'))
    
    # Check if email is already in use
    existing_user = User.query.filter_by(email=new_email).first()
    if existing_user and existing_user.id != current_user.id:
        flash('Email address is already in use', 'danger')
        return redirect(url_for('auth.settings'))
    
    try:
        current_user.email = new_email
        current_user.username = new_username
        db.session.commit()
        flash('Profile updated successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error updating profile', 'danger')
    
    return redirect(url_for('auth.settings'))

@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')
    
    # Validate inputs
    if not current_password or not new_password or not confirm_password:
        flash('All fields are required', 'danger')
        return redirect(url_for('auth.settings'))
    
    if new_password != confirm_password:
        flash('New passwords do not match', 'danger')
        return redirect(url_for('auth.settings'))
    
    if len(new_password) < 8:
        flash('Password must be at least 8 characters', 'danger')
        return redirect(url_for('auth.settings'))
    
    # Verify current password
    if not check_password_hash(current_user.password, current_password):
        flash('Current password is incorrect', 'danger')
        return redirect(url_for('auth.settings'))
    
    try:
        current_user.password = generate_password_hash(new_password)
        db.session.commit()
        flash('Password changed successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error changing password', 'danger')
    
    return redirect(url_for('auth.settings'))

@auth_bp.route('/delete-account')
@login_required
def delete_account():
    user_id = current_user.id  # Store user ID before logout
    
    try:
        # Get all history entries for this user
        history_entries = PdfHistory.query.filter_by(user_id=user_id).all()
        
        # Delete associated files first
        for entry in history_entries:
            files_to_delete = []
            
            # Handle PDF file
            if entry.filename:
                # Try multiple possible paths
                possible_paths = [
                    os.path.join(current_app.config.get('UPLOAD_FOLDER', 'uploads'), entry.filename),
                    entry.filename,  # In case it's already a full path
                    os.path.join('uploads', entry.filename)
                ]
                
                for pdf_path in possible_paths:
                    if os.path.exists(pdf_path):
                        files_to_delete.append(pdf_path)
                        break
            
            # Handle JSON file
            if entry.json_path:
                # Check if json_path is already a full path or needs to be joined
                if os.path.isabs(entry.json_path):
                    json_path = entry.json_path
                else:
                    json_path = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'uploads'), entry.json_path)
                
                if os.path.exists(json_path):
                    files_to_delete.append(json_path)
            
            # Handle LaTeX file
            if hasattr(entry, 'latex_path') and entry.latex_path:
                if os.path.isabs(entry.latex_path):
                    latex_path = entry.latex_path
                else:
                    latex_path = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'uploads'), entry.latex_path)
                
                if os.path.exists(latex_path):
                    files_to_delete.append(latex_path)
            
            # Delete files with better error handling
            for file_path in files_to_delete:
                try:
                    os.remove(file_path)
                    current_app.logger.info(f"Deleted file: {file_path}")
                except PermissionError:
                    current_app.logger.error(f"Permission denied deleting file: {file_path}")
                except FileNotFoundError:
                    current_app.logger.warning(f"File not found (already deleted?): {file_path}")
                except Exception as e:
                    current_app.logger.error(f"Unexpected error deleting file {file_path}: {str(e)}")
        
        # Delete database entries in correct order
        # First delete all PdfHistory entries
        PdfHistory.query.filter_by(user_id=user_id).delete()
        
        # Then delete the user
        user_to_delete = User.query.get(user_id)
        if user_to_delete:
            db.session.delete(user_to_delete)
        
        # Commit all database changes
        db.session.commit()
        
        # Logout user after successful deletion
        logout_user()
        
        flash('Your account has been permanently deleted', 'success')
        return redirect(url_for('auth.login'))
        
    except Exception as e:
        # Rollback any database changes
        db.session.rollback()
        current_app.logger.error(f"Error deleting account for user {user_id}: {str(e)}")
        flash(f'Error deleting account: {str(e)}', 'danger')
        return redirect(url_for('auth.settings'))
