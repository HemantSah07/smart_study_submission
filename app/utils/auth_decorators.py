from functools import wraps
from flask import abort, redirect, url_for, flash
from flask_login import current_user

SUPER_ADMIN_EMAIL = "hemantsah123456789@gmail.com"

def is_protected_primary_super_admin(user_or_email):
    """
    Centralized check to verify if a user or email is the protected Primary Super Admin.
    Primary Super Admin CANNOT be deleted, disabled, demoted, or modified by any user/endpoint.
    """
    if not user_or_email:
        return False
    if isinstance(user_or_email, str):
        email_str = user_or_email.strip().lower()
    elif hasattr(user_or_email, 'email') and user_or_email.email:
        email_str = user_or_email.email.strip().lower()
    else:
        return False
    return email_str == SUPER_ADMIN_EMAIL.lower()

def is_super_admin(user):
    """
    Returns True if the user is the Primary Super Admin or has role 'super_admin'.
    """
    if not user or not user.is_authenticated:
        return False
    if is_protected_primary_super_admin(user):
        return True
    return getattr(user, 'role', '') == 'super_admin'

def is_admin(user):
    """
    Returns True if the user is a Super Admin or Regular Admin (role in ['admin', 'super_admin']).
    """
    if not user or not user.is_authenticated:
        return False
    if is_super_admin(user):
        return True
    return getattr(user, 'role', '') in ['admin', 'super_admin']

def super_admin_required(f):
    """
    Route decorator requiring Super Admin privileges.
    Returns HTTP 403 Forbidden if accessed by Regular Admins or non-Super Admins.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=url_for('admin.dashboard')))
        if not is_super_admin(current_user):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """
    Route decorator requiring any Admin privileges (Super Admin or Regular Admin).
    Returns HTTP 403 Forbidden if accessed by Students or unauthenticated users.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if not is_admin(current_user):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function
