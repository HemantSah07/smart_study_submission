from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from app import db, bcrypt
from app.models import User, AuditLog, StudentProfile, AvailabilitySlot, University, EmailVerificationCode
from app.utils.timezone_utils import default_timezone_for_country
from datetime import datetime, timedelta
from urllib.parse import urlparse
import re

auth_bp = Blueprint("auth", __name__)

COUNTRY_CURRICULUM_MAP = {
    "Nepal": "NEB/CTEVT",
    "United States": "US Common Core/AP",
    "United Kingdom": "A-Levels/GCSE",
    "Australia": "HSC/VCE/SACE",
    "Canada": "Provincial/IB",
    "India": "CBSE/ICSE/State Boards",
}

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('student.dashboard'))
        
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        ip = request.remote_addr
        
        # Check lockout
        fifteen_mins_ago = datetime.utcnow() - timedelta(minutes=15)
        failed_attempts = AuditLog.query.filter(
            AuditLog.ip_address == ip,
            AuditLog.status == 'failed',
            AuditLog.timestamp >= fifteen_mins_ago
        ).count()
        
        if failed_attempts >= 5:
            flash("Too many failed attempts. Try again in 15 minutes", "danger")
            return render_template("auth/login.html")
            
        user = User.query.filter_by(email=email).first()
        
        if not user:
            log = AuditLog(ip_address=ip, email_attempted=email, status='failed')
            db.session.add(log)
            db.session.commit()
            flash("No account found with this email address", "danger")
            return render_template("auth/login.html")
            
        if not user.is_active:
            flash("Your account has been deactivated. Contact admin", "danger")
            return render_template("auth/login.html")

        # Seed accounts created by load_data.py are not loginable.
        if getattr(user, 'is_seed_account', False):
            log = AuditLog(ip_address=ip, email_attempted=email, status='failed')
            db.session.add(log)
            db.session.commit()
            flash("No account found with this email address", "danger")
            return render_template("auth/login.html")
            
        if bcrypt.check_password_hash(user.password_hash, password):
            log = AuditLog(ip_address=ip, email_attempted=email, status='success')
            db.session.add(log)
            db.session.commit()
            
            login_user(user)
            flash("Login successful!", "success")
            next_page = request.args.get('next')
            if next_page:
                parsed = urlparse(next_page)
                if not parsed.scheme and not parsed.netloc and next_page.startswith('/') and not next_page.startswith('//'):
                    return redirect(next_page)
            if user.is_admin:
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('student.dashboard'))
        else:
            log = AuditLog(ip_address=ip, email_attempted=email, status='failed')
            db.session.add(log)
            db.session.commit()
            flash("Incorrect password. Please try again", "danger")
            
    return render_template("auth/login.html")

def check_password_strength(password):
    score = 0
    if re.search(r'[A-Z]', password): score += 1
    if re.search(r'[a-z]', password): score += 1
    if re.search(r'[0-9]', password): score += 1
    if re.search(r'[^a-zA-Z0-9]', password): score += 1
    return score >= 4 and len(password) >= 8


@auth_bp.route("/send-verification-ajax", methods=["POST"])
def send_verification_ajax():
    email = request.form.get("email", "").strip().lower()
    if not email:
        return jsonify({"status": "error", "message": "Email address is required"}), 400
        
    # Check if duplicate email
    if User.query.filter(db.func.lower(User.email) == email).first():
        return jsonify({"status": "error", "message": "This email is already registered. Please login"}), 400
        
    # Format & Deliverability check
    from app.utils.email_verification import verify_email
    verification = verify_email(email)
    if not verification.get("is_valid_format") or verification.get("deliverability") == "UNDELIVERABLE":
        return jsonify({"status": "error", "message": "This email address doesn't appear to be valid or deliverable, please check and try again"}), 400
        
    # Generate code
    import secrets
    code = "".join(secrets.choice("0123456789") for _ in range(6))
    
    now = datetime.utcnow()
    expires = now + timedelta(minutes=10)
    
    # Clear existing code
    EmailVerificationCode.query.filter_by(email=email).delete()
    
    verification_code = EmailVerificationCode(
        email=email,
        code=code,
        created_at=now,
        expires_at=expires,
        verified=False,
        attempts=0
    )
    db.session.add(verification_code)
    db.session.commit()
    
    # Send email
    from flask_mail import Message
    from app import mail
    try:
        msg = Message(
            subject="Verify Your Email - Smart Study",
            recipients=[email],
            body=f"Your Smart Study verification code is: {code}. This code expires in 10 minutes."
        )
        mail.send(msg)
        return jsonify({"status": "success", "message": "Verification email sent. Please check your inbox."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to send verification email: {str(e)}. Please try again later."}), 500

@auth_bp.route("/verify-code-ajax", methods=["POST"])
def verify_code_ajax():
    email = request.form.get("email", "").strip().lower()
    user_code = request.form.get("code", "").strip()
    
    if not email or not user_code:
        return jsonify({"status": "error", "message": "Email and verification code are required"}), 400
        
    code_record = EmailVerificationCode.query.filter_by(email=email).order_by(EmailVerificationCode.created_at.desc()).first()
    if not code_record:
        return jsonify({"status": "error", "message": "No verification code found. Please request a new one."}), 400
        
    # Expiration check
    if datetime.utcnow() > code_record.expires_at:
        return jsonify({"status": "error", "message": "Verification code has expired. Please request a new one."}), 400
        
    # Attempt limit check
    if code_record.attempts >= 5:
        return jsonify({"status": "error", "message": "Too many failed attempts. Please request a new code."}), 400
        
    # Code check
    if code_record.code != user_code:
        code_record.attempts += 1
        db.session.commit()
        remaining = 5 - code_record.attempts
        if remaining <= 0:
            return jsonify({"status": "error", "message": "Too many failed attempts. Please request a new code."}), 400
        else:
            return jsonify({"status": "error", "message": f"Invalid verification code. {remaining} attempt(s) remaining."}), 400
            
    code_record.verified = True
    db.session.commit()
    
    session['verified_email'] = email
    return jsonify({"status": "success", "message": "✓ Email Verified"})

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('student.dashboard'))
        
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password") or request.form.get("admin_password")
        confirm_password = request.form.get("confirm_password") or request.form.get("admin_confirm_password")
        account_role = request.form.get("role", "student").strip().lower()
        country = request.form.get("country", "Nepal").strip()
        level_of_study = request.form.get("level_of_study", "").strip()
        
        # --- ADMIN REGISTRATION REQUEST WORKFLOW ---
        if account_role == "admin":
            from app.models import SUPER_ADMIN_EMAIL, AdminRegistrationRequest, AdminActivityLog
            
            if email == SUPER_ADMIN_EMAIL.lower():
                flash("The Primary Super Admin email address cannot be used as an applicant personal email.", "danger")
                return redirect(url_for('auth.register'))

            if not full_name or not email or not password or not confirm_password:
                flash("All required fields (Full Name, Personal Email, Password) must be provided.", "danger")
                return redirect(url_for('auth.register'))
                
            if password != confirm_password:
                flash("Passwords do not match.", "danger")
                return redirect(url_for('auth.register'))
                
            if not check_password_strength(password):
                flash("Password must be at least 8 characters long and contain uppercase, lowercase, numbers, and special characters.", "danger")
                return redirect(url_for('auth.register'))

            # Duplicate email check in active users
            if User.query.filter(db.func.lower(User.email) == email).first():
                flash("This email is already registered in Smart Study. Please log in.", "danger")
                return redirect(url_for('auth.register'))

            # Check if pending request exists
            existing_req = AdminRegistrationRequest.query.filter(
                db.func.lower(AdminRegistrationRequest.email) == email,
                AdminRegistrationRequest.status == 'PENDING'
            ).first()
            if existing_req:
                flash("An admin registration request for this email is already pending approval from the Super Admin.", "warning")
                return redirect(url_for('auth.verify_admin_code', email=email))

            hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
            admin_req = AdminRegistrationRequest(
                full_name=full_name,
                email=email,
                password_hash=hashed_pw,
                requested_role='admin',
                status='PENDING'
            )
            db.session.add(admin_req)
            db.session.commit()

            # Notify Super Admin via Email
            from flask_mail import Message
            from app import mail
            try:
                msg = Message(
                    subject="New Admin Registration Request - Smart Study",
                    recipients=[SUPER_ADMIN_EMAIL],
                    body=(
                        f"New Admin Registration Request\n\n"
                        f"Applicant Name: {full_name}\n"
                        f"Applicant Personal Email: {email}\n"
                        f"Requested Role: Regular Admin\n"
                        f"Request Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n"
                        f"An applicant has requested access to the Smart Study Admin Dashboard.\n"
                        f"Please review and approve this request from the Super Admin Dashboard."
                    )
                )
                mail.send(msg)
            except Exception as e:
                print(f"[Mail Error] Failed to dispatch admin request email to Super Admin: {e}")

            flash(
                f"Admin registration request submitted for {email}! Approval request sent to Super Admin. "
                f"Upon approval, a 24-hour verification code will be sent to your personal email address.",
                "info"
            )
            return redirect(url_for('auth.verify_admin_code', email=email))



        # --- STUDENT REGISTRATION WORKFLOW ---
        # Check if email is already verified in this session (new flow)
        session_verified_email = session.get('verified_email', '').strip().lower()
        is_verified_inline = (session_verified_email and email == session_verified_email)

        
        # If not verified inline, we fall back to the old registration/redirect flow (for unit tests / compatibility)
        if not is_verified_inline:
            # Case-insensitive duplicate check
            if User.query.filter(db.func.lower(User.email) == email).first():
                flash("This email is already registered. Please login", "danger")
                return redirect(url_for('auth.register'))
                
            if not check_password_strength(password):
                flash("Password does not meet strength requirements", "danger")
                return redirect(url_for('auth.register'))
                
            # Exclude program/duration/university for lower classes
            program = request.form.get("program") if level_of_study in ("Class 11", "Class 12", "Bachelors", "Masters") else ""
            semester = request.form.get("semester") if level_of_study in ("Bachelors", "Masters") else ""
            
            university = ""
            if level_of_study in ("Bachelors", "Masters"):
                uni_select = request.form.get("university_select", "").strip()
                uni_custom = request.form.get("university_custom", "").strip()
                if uni_select in ("Foreign-Affiliated", "Other"):
                    university = f"{uni_select}: {uni_custom}" if uni_custom else uni_select
                else:
                    university = uni_select
            
            import uuid
            student_number = f"STU-{uuid.uuid4().hex[:8].upper()}"
            
            year_of_study = 1
            if semester:
                if "Semester" in semester:
                    try:
                        sem_num = int(semester.replace("Semester", "").strip())
                        year_of_study = (sem_num - 1) // 2 + 1
                    except ValueError:
                        pass
                elif "Professional Year" in semester:
                    try:
                        year_of_study = int(semester.replace("Professional Year", "").strip())
                    except ValueError:
                        pass
            
            from app.utils.email_verification import verify_email
            verification = verify_email(email)
            if not verification.get("is_valid_format") or verification.get("deliverability") == "UNDELIVERABLE":
                flash("This email address doesn't appear to be valid or deliverable, please check and try again", "danger")
                return redirect(url_for('auth.register'))
                
            import secrets
            code = "".join(secrets.choice("0123456789") for _ in range(6))
            
            now = datetime.utcnow()
            expires = now + timedelta(minutes=10)
            
            EmailVerificationCode.query.filter_by(email=email).delete()
            
            verification_code = EmailVerificationCode(
                email=email,
                code=code,
                created_at=now,
                expires_at=expires,
                verified=False,
                attempts=0
            )
            db.session.add(verification_code)
            db.session.commit()
            
            session['temp_registration'] = {
                'email': email,
                'full_name': full_name,
                'password': password,
                'country': country,
                'curriculum': COUNTRY_CURRICULUM_MAP.get(country, "National"),
                'level_of_study': level_of_study,
                'program': program,
                'semester': semester,
                'university': university,
                'student_number': student_number,
                'year_of_study': year_of_study,
                'email_verified_status': verification.get("deliverability", "unknown").lower()
            }
            session['resend_count'] = 0
            session['last_resend_time'] = None
            
            from flask_mail import Message
            from app import mail
            try:
                msg = Message(
                    subject="Verify Your Email - Smart Study",
                    recipients=[email],
                    body=f"Your Smart Study verification code is: {code}. This code expires in 10 minutes."
                )
                mail.send(msg)
                flash("A 6-digit verification code has been sent to your email.", "info")
            except Exception as e:
                flash(f"Failed to send verification email: {e}. Please try again later.", "danger")
                return redirect(url_for('auth.register'))
                
            return redirect(url_for('auth.verify_email_code', email=email))
            
        # --- NEW FLOW (verified inline) ---
        code_record = EmailVerificationCode.query.filter_by(email=email).order_by(EmailVerificationCode.created_at.desc()).first()
        if not code_record or not code_record.verified or datetime.utcnow() > code_record.expires_at:
            flash("Please verify your email address before registering.", "danger")
            return redirect(url_for('auth.register'))
            
        # Email uniqueness check
        if User.query.filter(db.func.lower(User.email) == email).first():
            flash("This email is already registered. Please login", "danger")
            return redirect(url_for('auth.register'))
            
        if not full_name:
            flash("Full Name is required.", "danger")
            return redirect(url_for('auth.register'))
            
        if not check_password_strength(password):
            flash("Password does not meet strength requirements", "danger")
            return redirect(url_for('auth.register'))
            
        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for('auth.register'))
            
        curriculum = COUNTRY_CURRICULUM_MAP.get(country, "National")
        
        university_type = ""
        university_country = ""
        university = ""
        program = ""
        program_duration = ""
        semester = ""
        
        if level_of_study in ("Bachelors", "Masters"):
            university_type = request.form.get("university_type", "").strip()
            program = request.form.get("program", "").strip()
            program_duration = request.form.get("program_duration", "").strip()
            
            if not university_type or not program:
                flash("Academic program and university settings are required.", "danger")
                return redirect(url_for('auth.register'))
                
            if university_type == "Foreign":
                university_country = request.form.get("university_country", "").strip()
                university = request.form.get("foreign_university", "").strip()
                if not university_country or not university:
                    flash("Foreign country and university selections are required.", "danger")
                    return redirect(url_for('auth.register'))
            else: # National
                university_type = "National"
                university_country = ""
                uni_select = request.form.get("university_select", "").strip()
                if uni_select in ("Foreign-Affiliated", "Other"):
                    uni_custom = request.form.get("university_custom", "").strip()
                    university = f"{uni_select}: {uni_custom}" if uni_custom else uni_select
                else:
                    university = uni_select
                if not university:
                    flash("University selection is required.", "danger")
                    return redirect(url_for('auth.register'))
                    
            semester = f"Semester 1"
            
        import uuid
        student_number = f"STU-{uuid.uuid4().hex[:8].upper()}"
        
        # Create User record
        from app.utils.email_verification import verify_email
        verification = verify_email(email)
        status = verification.get("deliverability", "unknown").lower()
        if status not in ('deliverable', 'risky', 'unknown', 'undeliverable'):
            status = 'deliverable'

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(
            username=email,
            full_name=full_name,
            email=email,
            password_hash=hashed_password,
            role='student',
            email_verified_status=status
        )
        db.session.add(new_user)
        db.session.flush()
        
        # Create StudentProfile record
        profile = StudentProfile(
            user_id=new_user.id,
            student_number=student_number,
            program=program,
            year_of_study=1,
            level_of_study=level_of_study,
            study_level=level_of_study,
            semester=semester,
            country=country,
            university=university,
            university_type=university_type,
            university_country=university_country,
            timezone=default_timezone_for_country(country),
            curriculum=curriculum,
            cumulative_gpa=0.0,
            program_duration=program_duration
        )
        db.session.add(profile)
        
        # Seed availability slots
        days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        default_slots = [
            {"start": "00:00", "end": "06:00", "category": "Sleep"},
            {"start": "08:00", "end": "17:00", "category": "Class/Academic"},
            {"start": "22:00", "end": "23:59", "category": "Sleep"}
        ]
        for day in days:
            for ds in default_slots:
                slot = AvailabilitySlot(
                    user_id=new_user.id,
                    day_of_week=day,
                    start_time=ds["start"],
                    end_time=ds["end"],
                    slot_type="Sleep" if ds["category"] == "Sleep" else "Busy",
                    category=ds["category"],
                    is_overnight=ds["start"] > ds["end"],
                )
                db.session.add(slot)
                
        db.session.commit()
        
        # Log student in and clear temp data
        login_user(new_user)
        session.pop('verified_email', None)
        flash("Registration successful!", "success")
        return redirect(url_for('student.dashboard'))
        
    return render_template("auth/register.html", active_universities=University.query.filter_by(is_active=True).order_by(University.sort_order).all())


@auth_bp.route("/verify-email", methods=["GET", "POST"])
def verify_email_code():
    from flask import session
    email = request.args.get("email")
    if not email:
        flash("Email parameter missing.", "danger")
        return redirect(url_for('auth.register'))
        
    temp_data = session.get('temp_registration')
    if not temp_data or temp_data.get('email') != email:
        flash("Session expired or invalid email. Please register again.", "danger")
        return redirect(url_for('auth.register'))
        
    resend_count = session.get('resend_count', 0)
    
    # Calculate remaining time for the 60-second resend cooldown
    time_remaining = 0
    last_resend_time_str = session.get('last_resend_time')
    if last_resend_time_str:
        try:
            last_resend_time = datetime.fromisoformat(last_resend_time_str)
            elapsed = (datetime.utcnow() - last_resend_time).total_seconds()
            if elapsed < 60:
                time_remaining = int(60 - elapsed)
        except Exception:
            pass

    code_record = EmailVerificationCode.query.filter_by(email=email).order_by(EmailVerificationCode.created_at.desc()).first()
    if not code_record:
        flash("No verification code found. Please request a new one.", "danger")
        return redirect(url_for('auth.register'))
        
    # Expiration check
    if datetime.utcnow() > code_record.expires_at:
        session.pop('temp_registration', None)
        flash("Verification code has expired. Please register again.", "danger")
        return redirect(url_for('auth.register'))

    if request.method == "POST":
        user_code = request.form.get("code", "").strip()
        
        # 1. Attempt limit check
        if code_record.attempts >= 5:
            flash("Too many failed attempts. Please request a new code.", "danger")
            return render_template("auth/verify_email.html", email=email, resend_count=resend_count, time_remaining=time_remaining)
            
        # 2. Code check
        if code_record.code != user_code:
            code_record.attempts += 1
            db.session.commit()
            
            remaining = 5 - code_record.attempts
            if remaining <= 0:
                flash("Too many failed attempts. Please request a new code.", "danger")
            else:
                flash(f"Invalid verification code. {remaining} attempt(s) remaining.", "danger")
            return render_template("auth/verify_email.html", email=email, resend_count=resend_count, time_remaining=time_remaining)
            
        # Successful code verification
        code_record.verified = True
        db.session.commit()
        
        # Create User record
        hashed_password = bcrypt.generate_password_hash(temp_data['password']).decode('utf-8')
        new_user = User(
            username=temp_data['email'].lower(),
            full_name=temp_data['full_name'],
            email=temp_data['email'],
            password_hash=hashed_password,
            role='student',
            email_verified_status=temp_data['email_verified_status']
        )
        db.session.add(new_user)
        db.session.flush()
        
        # Create StudentProfile record
        profile = StudentProfile(
            user_id=new_user.id,
            student_number=temp_data['student_number'],
            program=temp_data['program'],
            year_of_study=temp_data['year_of_study'],
            level_of_study=temp_data['level_of_study'],
            study_level=temp_data['level_of_study'],
            semester=temp_data['semester'],
            country=temp_data['country'],
            university=temp_data['university'],
            timezone=default_timezone_for_country(temp_data['country']),
            curriculum=temp_data['curriculum'],
            cumulative_gpa=0.0
        )
        db.session.add(profile)
        
        # Seed availability slots
        days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        default_slots = [
            {"start": "00:00", "end": "06:00", "category": "Sleep"},
            {"start": "08:00", "end": "17:00", "category": "Class/Academic"},
            {"start": "22:00", "end": "23:59", "category": "Sleep"}
        ]
        for day in days:
            for ds in default_slots:
                slot = AvailabilitySlot(
                    user_id=new_user.id,
                    day_of_week=day,
                    start_time=ds["start"],
                    end_time=ds["end"],
                    slot_type="Sleep" if ds["category"] == "Sleep" else "Busy",
                    category=ds["category"],
                    is_overnight=ds["start"] > ds["end"],
                )
                db.session.add(slot)
                
        db.session.commit()
        
        # Log student in and clear temp data
        login_user(new_user)
        session.pop('temp_registration', None)
        flash("Email verified and account created successfully!", "success")
        return redirect(url_for('student.dashboard'))
        
    return render_template("auth/verify_email.html", email=email, resend_count=resend_count, time_remaining=time_remaining)


@auth_bp.route("/resend-code", methods=["POST"])
def resend_verification_code():
    from flask import session
    email = request.args.get("email")
    if not email:
        flash("Email parameter missing.", "danger")
        return redirect(url_for('auth.register'))
        
    temp_data = session.get('temp_registration')
    if not temp_data or temp_data.get('email') != email:
        flash("Session expired or invalid email. Please register again.", "danger")
        return redirect(url_for('auth.register'))
        
    resend_count = session.get('resend_count', 0)
    
    # 1. Count limit
    if resend_count >= 3:
        flash("Maximum resend attempts reached (3). Please complete verification or start over.", "danger")
        return redirect(url_for('auth.verify_email_code', email=email))
        
    # 2. Wait limit check
    last_resend_time_str = session.get('last_resend_time')
    if last_resend_time_str:
        try:
            last_resend_time = datetime.fromisoformat(last_resend_time_str)
            elapsed = (datetime.utcnow() - last_resend_time).total_seconds()
            if elapsed < 60:
                flash(f"Please wait {int(60 - elapsed)} second(s) before resending.", "danger")
                return redirect(url_for('auth.verify_email_code', email=email))
        except Exception:
            pass

    # 3. Generate new code and save
    import secrets
    code = "".join(secrets.choice("0123456789") for _ in range(6))
    
    now = datetime.utcnow()
    expires = now + timedelta(minutes=10)
    
    # Clean previous codes
    EmailVerificationCode.query.filter_by(email=email).delete()
    
    verification_code = EmailVerificationCode(
        email=email,
        code=code,
        created_at=now,
        expires_at=expires,
        verified=False,
        attempts=0
    )
    db.session.add(verification_code)
    db.session.commit()
    
    session['resend_count'] = resend_count + 1
    session['last_resend_time'] = datetime.utcnow().isoformat()
    
    # 4. Send code
    from flask_mail import Message
    from app import mail
    try:
        msg = Message(
            subject="Verify Your Email - Smart Study",
            recipients=[email],
            body=f"Your Smart Study verification code is: {code}. This code expires in 10 minutes."
        )
        mail.send(msg)
        flash("A new 6-digit verification code has been sent to your email.", "success")
    except Exception as e:
        flash(f"Failed to send verification email: {e}. Please try again later.", "danger")
        
    return redirect(url_for('auth.verify_email_code', email=email))

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for('auth.login'))


@auth_bp.route("/verify-admin-code", methods=["GET", "POST"])
def verify_admin_code():
    """
    Verification page for admin applicants who received an approval code from Super Admin.
    Account is only activated AFTER successful code verification.
    """
    from app.models import AdminRegistrationRequest, AdminActivityLog
    email = request.args.get("email", "").strip().lower()

    if request.method == "POST":
        email_submitted = request.form.get("email", "").strip().lower()
        code_submitted = request.form.get("verification_code", "").strip()

        if not email_submitted or not code_submitted:
            flash("Email and 6-digit verification code are required.", "danger")
            return render_template("auth/verify_admin_code.html", email=email_submitted)

        # Look up approved request matching email
        admin_req = AdminRegistrationRequest.query.filter(
            db.func.lower(AdminRegistrationRequest.email) == email_submitted,
            AdminRegistrationRequest.status == 'APPROVED',
            AdminRegistrationRequest.code_used == False
        ).order_by(AdminRegistrationRequest.actioned_at.desc()).first()

        if not admin_req:
            flash("No approved admin registration request found for this email address. Please ensure Super Admin has approved your request.", "danger")
            return render_template("auth/verify_admin_code.html", email=email_submitted)

        # Expiration check
        if admin_req.code_expires_at and datetime.utcnow() > admin_req.code_expires_at:
            flash("The verification code has expired (24-hour limit). Please request re-approval from the Super Admin.", "danger")
            return render_template("auth/verify_admin_code.html", email=email_submitted)

        # Code verification
        if admin_req.verification_code != code_submitted:
            flash("Invalid verification code. Please check the code sent to your email.", "danger")
            return render_template("auth/verify_admin_code.html", email=email_submitted)

        # Code is valid — Activate account!
        admin_req.code_used = True
        
        # Check if user record already exists
        existing_user = User.query.filter(db.func.lower(User.email) == email_submitted).first()
        if existing_user:
            existing_user.role = 'admin'
            existing_user.is_active = True
            existing_user.password_hash = admin_req.password_hash
        else:
            new_admin = User(
                username=email_submitted,
                full_name=admin_req.full_name,
                email=email_submitted,
                password_hash=admin_req.password_hash,
                role='admin',
                is_active=True,
                is_seed_account=False
            )
            db.session.add(new_admin)

        db.session.commit()

        # Log activation
        try:
            target_user = User.query.filter(db.func.lower(User.email) == email_submitted).first()
            log = AdminActivityLog(
                admin_user_id=admin_req.actioned_by_id or target_user.id,
                action="activated_regular_admin",
                entity_type="User",
                entity_id=target_user.id,
                detail=f"Applicant {admin_req.full_name} ({email_submitted}) verified code and activated Regular Admin account"
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            db.session.rollback()

        flash("✓ Admin Account Verified & Activated! You may now log in with your administrative credentials.", "success")
        return redirect(url_for('auth.login'))

    return render_template("auth/verify_admin_code.html", email=email)

